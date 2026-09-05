# -*- coding: utf-8 -*-
"""Kryon 自动化 —— 核心引擎。

实现「自动化」能力（触发器 + 规则集 + 行动 + 恢复），
并支持间隔触发、今天是/时间晚于/读标志、当前教师/下节教师、设标志等扩展。

模型（每条自动化 = 触发器中任一 + 规则集过滤 + 行动序列）：
    triggers[]  任意一个触发即可
    ruleset     规则集：enabled / mode(all|any) / reversed / rules[]
    actions[]   顺序执行（可含 wait）
    revert      是否在逆事件或规则集不再满足时自动恢复

触发器 / 规则 / 行动类型见文件底部常量表（与 QML 顺序一致）。
"""

from __future__ import annotations

import datetime
import json
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QObject, QTimer, Signal
from loguru import logger

# ── 触发器类型（顺序 = QML 下拉顺序）──────────────────────────
T_TIME = "time"                 # 定时（HH:MM + 星期）
T_INTERVAL = "interval"         # 间隔触发（每 N 秒）
T_CLASS_START = "class_start"   # 上课时
T_CLASS_END = "class_end"       # 下课时
T_BREAK_START = "break_start"   # 课间休息时
T_AFTER_SCHOOL = "after_school" # 放学时
T_STATUS_CHANGE = "status_change"  # 时间状态变化时
T_BEFORE_CLASS = "before_class" # 上课前 N 秒
T_APP_START = "app_start"       # 应用启动时
T_SIGNAL = "signal"             # 收到信号
TRIGGER_TYPES = (T_TIME, T_INTERVAL, T_CLASS_START, T_CLASS_END, T_BREAK_START,
                 T_AFTER_SCHOOL, T_STATUS_CHANGE, T_BEFORE_CLASS, T_APP_START, T_SIGNAL)

# 触发器逆事件（用于恢复）
TRIGGER_INVERSE = {
    T_CLASS_START: T_CLASS_END,
    T_BREAK_START: T_CLASS_START,
    T_AFTER_SCHOOL: None,
}

# ── 规则类型（顺序 = QML 下拉顺序）────────────────────────────
R_ALWAYS_TRUE = "always_true"
R_ALWAYS_FALSE = "always_false"
R_TODAY_IS = "today_is"           # 今天是…
R_LATER_THAN = "later_than"       # 时间晚于…
R_CURRENT_SUBJECT = "current_subject"
R_NEXT_SUBJECT = "next_subject"
R_PREV_SUBJECT = "prev_subject"
R_CURRENT_STATUS = "current_status"
R_FOREGROUND_WINDOW = "foreground_window"
R_FLAG_IS = "flag_is"             # 读标志
R_CURRENT_TEACHER = "current_teacher"  # 当前教师是
R_NEXT_TEACHER = "next_teacher"        # 下节课教师是
RULE_TYPES = (R_ALWAYS_TRUE, R_ALWAYS_FALSE, R_TODAY_IS, R_LATER_THAN,
              R_CURRENT_SUBJECT, R_NEXT_SUBJECT, R_PREV_SUBJECT, R_CURRENT_STATUS,
              R_FOREGROUND_WINDOW, R_FLAG_IS, R_CURRENT_TEACHER, R_NEXT_TEACHER)

# ── 行动类型（顺序 = QML 下拉顺序）────────────────────────────
A_RUN = "run"                     # 运行命令/程序/网址
A_NOTIFY = "notify"               # 显示提醒
A_WAIT = "wait"                   # 等待
A_BROADCAST = "broadcast"         # 广播信号
A_SET_FLAG = "set_flag"           # 设标志
A_SET_CONFIG = "set_config"       # 设置配置项（主题/锚点/层级/隐藏/迷你…）
A_LOCK = "lock"                   # 锁定配置项
A_RESTART = "restart"             # 重启主程序
ACTION_TYPES = (A_RUN, A_NOTIFY, A_WAIT, A_BROADCAST, A_SET_FLAG,
                A_SET_CONFIG, A_LOCK, A_RESTART)

# set_config 键白名单 → (类型, 默认值)
CONFIG_KEYS: dict[str, str] = {
    "preferences.mini_mode": "bool",
    "preferences.current_theme": "str",
    "preferences.opacity": "float",
    "preferences.scale_factor": "float",
    "preferences.lighting_effect": "bool",
    "preferences.countdown_precision": "str",
    "preferences.widgets_anchor": "str",
    "preferences.widgets_offset_x": "int",
    "preferences.widgets_offset_y": "int",
    "preferences.widgets_layer": "str",
    "preferences.current_preset": "str",
    "interactions.hide.state": "bool",
    "interactions.hide.in_class": "bool",
    "interactions.hide.maximized": "bool",
    "interactions.hide.fullscreen": "bool",
    "interactions.hide.action": "str",
    "interactions.tapped_action": "str",
    "interactions.hover_fade": "bool",
    "notifications.enabled": "bool",
    "notifications.volume": "float",
}

# 可逆行动（支持恢复）
REVERTIBLE_ACTIONS = (A_SET_CONFIG, A_LOCK, A_SET_FLAG)


def coerce(value: Any, kind: str) -> Any:
    """把配置值字符串解析为对应类型。"""
    s = str(value).strip().lower()
    if kind == "bool":
        if s in ("1", "true", "yes", "on", "开", "是"):
            return True
        if s in ("0", "false", "no", "off", "关", "否"):
            return False
        return bool(value)
    if kind == "int":
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0
    if kind == "float":
        try:
            return float(value)
        except (TypeError, ValueError):
            return 1.0
    return str(value).strip()


class RuleEngine(QObject):
    """自动化规则引擎（纯逻辑，不依赖主程序 src.core）。"""

    signalBus = Signal(str)  # 广播信号（收到信号触发器 + 广播信号行动）

    def __init__(self, api, storage_path: Path):
        super().__init__()
        self._api = api
        self._storage = storage_path
        self._rules: list[dict] = []
        self._flags: dict[str, str] = {}
        self._active: dict[str, dict] = {}   # uid -> {"keys": {path: orig}, "rule": rule}
        self._flag_originals: dict[str, Optional[str]] = {}
        self._provider = None
        self._prev_status = ""

        self._tick_timer = QTimer(self)   # 兜底 tick（若未注册官方任务）
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self.update)
        self._tick_timer.start()

        try:
            self._api.runtime.statusChanged.connect(self.on_status_changed)
        except Exception as e:
            logger.warning("[automations] 连接状态信号失败: {}", e)

        # 广播信号 → 收到信号触发器
        self.signalBus.connect(self._on_broadcast)

    def _on_broadcast(self, name: str) -> None:
        for rule in self._rules:
            if not rule.get("enabled"):
                continue
            if any(t.get("type") == T_SIGNAL and str(t.get("p1") or "") == name
                   for t in (rule.get("triggers") or [])):
                logger.info("[automations] 收到信号 {} 触发: {}", name, rule.get("name"))
                self._maybe_fire(rule, {"type": T_SIGNAL})

    # ── 数据 ────────────────────────────────────────────────

    def load(self) -> None:
        try:
            if self._storage.is_file():
                data = json.loads(self._storage.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    if isinstance(data.get("rules"), list):
                        self._rules = [self._clean_rule(r) for r in data["rules"] if isinstance(r, dict)]
                    self._flags = {str(k): str(v) for k, v in (data.get("flags") or {}).items()}
        except Exception as e:
            logger.warning("[automations] 读取配置失败: {}", e)
        self._prev_status = self._safe_status()

    def save(self) -> bool:
        try:
            self._storage.parent.mkdir(parents=True, exist_ok=True)
            payload = {"rules": self._rules, "flags": self._flags}
            self._storage.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
            return True
        except Exception as e:
            logger.warning("[automations] 保存失败: {}", e)
            return False

    def get_rules(self) -> list[dict]:
        return self._rules

    def set_rules(self, rules) -> bool:
        if not isinstance(rules, list):
            return False
        self._rules = [self._clean_rule(r) for r in rules if isinstance(r, dict)]
        self._active.clear()
        return self.save()

    def get_flags(self) -> dict[str, str]:
        return self._flags

    def fire_now(self, index: int) -> bool:
        try:
            rule = self._rules[int(index)]
        except (IndexError, ValueError, TypeError):
            return False
        logger.info("[automations] 手动触发: {}", rule.get("name"))
        self._fire(rule)
        return True

    # ── 每 tick 调度（官方 AutomationTask.update 每秒调用）─────

    def update(self) -> None:
        now = datetime.datetime.now()
        try:
            for rule in self._rules:
                if not rule.get("enabled"):
                    continue
                for trig in rule.get("triggers") or []:
                    if self._check_trigger(rule, trig, now):
                        self._maybe_fire(rule, trig)
                        break
        except Exception as e:
            logger.warning("[automations] tick 异常: {}", e)
        # 规则集持续监测：已执行的自动化在规则集变 false 时恢复
        self._revert_scan()

    # ── 触发器检测 ──────────────────────────────────────────

    def _check_trigger(self, rule: dict, trig: dict, now: datetime.datetime) -> bool:
        t = trig.get("type")
        if t == T_TIME:
            m = re.match(r"^(\d{1,2}):(\d{2})$", str(trig.get("p1") or "").strip())
            if not m:
                return False
            if (int(m.group(1)), int(m.group(2))) != (now.hour, now.minute):
                return False
            days = str(trig.get("p2") or "").strip()
            if days and str(now.isoweekday()) not in re.split(r"[,，、\s]+", days):
                return False
            fp = f"{now.strftime('%Y%m%d')}-{trig.get('p1')}-{days}"
            if trig.get("_fp") == fp:
                return False
            trig["_fp"] = fp
            return True
        if t == T_INTERVAL:
            secs = max(1, int(float(trig.get("p1") or 60)))
            last = float(trig.get("_lt") or 0)
            if now.timestamp() - last >= secs:
                trig["_lt"] = now.timestamp()
                return True
            return False
        if t == T_BEFORE_CLASS:
            secs = max(0, int(float(trig.get("p1") or 30)))
            nxt = self._next_entry()
            if not nxt:
                return False
            try:
                start = datetime.datetime.strptime(nxt.get("startTime", ""), "%H:%M").time()
                start_dt = datetime.datetime.combine(now.date(), start)
                delta = (start_dt - now).total_seconds()
            except ValueError:
                return False
            if 0 <= delta <= secs:
                fp = f"{now.strftime('%Y%m%d')}-{nxt.get('id')}"
                if trig.get("_fp") == fp:
                    return False
                trig["_fp"] = fp
                return True
            return False
        return False

    def _next_entry(self) -> Optional[dict]:
        try:
            entries = self._api.runtime.next_entries or []
            return entries[0] if entries else None
        except Exception:
            return None

    # ── 课程事件（statusChanged 信号）────────────────────────

    def on_status_changed(self, status: str) -> None:
        now = status or ""
        prev = self._prev_status
        self._prev_status = now

        def fire(ttype: str) -> None:
            for rule in self._rules:
                if not rule.get("enabled"):
                    continue
                if any(tr.get("type") == ttype for tr in (rule.get("triggers") or [])):
                    self._maybe_fire(rule, {"type": ttype})

        was_class = prev in ("class", "activity")
        is_class = now in ("class", "activity")

        if T_STATUS_CHANGE in (t.get("type") for r in self._rules for t in r.get("triggers") or []):
            fire(T_STATUS_CHANGE)
        if not was_class and is_class:
            fire(T_CLASS_START)
        elif was_class and not is_class:
            fire(T_CLASS_END)
        if now == "break":
            fire(T_BREAK_START)
        if now == "free" and prev and prev != "free":
            fire(T_AFTER_SCHOOL)

        # 逆事件恢复
        for uid, rec in list(self._active.items()):
            rule = rec["rule"]
            if rule.get("revert") and any(tr.get("type") == T_CLASS_START
                                          for tr in rule.get("triggers") or []):
                if T_CLASS_END in (t.get("type") for t in rule.get("triggers") or []):
                    continue  # 有显式下课触发器则由其自行处理
                if not was_class and is_class:
                    pass  # 刚上课，不恢复
                elif was_class and not is_class:
                    self._revert(uid)

        self._revert_scan()

    # ── 触发执行 ────────────────────────────────────────────

    def _maybe_fire(self, rule: dict, trig: dict) -> None:
        if not self._evaluate_ruleset(rule):
            return
        self._fire(rule)

    def _fire(self, rule: dict) -> None:
        uid = rule.get("uid")
        if rule.get("revert") and uid not in self._active:
            self._active[uid] = {"keys": {}, "flags": {}, "locked": [], "rule": rule}
        logger.info("[automations] 触发: {}", rule.get("name"))
        self._exec_at(rule.get("actions") or [], 0, 50, uid)

    def _exec_at(self, actions: list, index: int, delay_ms: int, uid: Optional[str] = None) -> None:
        if index >= len(actions):
            return
        QTimer.singleShot(delay_ms, lambda: self._step(actions, index, uid))

    def _step(self, actions: list, index: int, uid: Optional[str]) -> None:
        action = actions[index] or {}
        atype = action.get("type")
        wait_ms = 0
        try:
            if atype == A_RUN:
                self._do_run(action)
            elif atype == A_NOTIFY:
                self._do_notify(action)
            elif atype == A_BROADCAST:
                self.signalBus.emit(str(action.get("p1") or ""))
            elif atype == A_SET_FLAG:
                self._do_set_flag(action, uid)
            elif atype == A_SET_CONFIG:
                self._do_set_config(action, uid)
            elif atype == A_LOCK:
                self._do_lock(action, uid)
            elif atype == A_RESTART:
                self._api.application.restart()
            elif atype == A_WAIT:
                wait_ms = max(0, int(float(action.get("p1") or 0)) * 1000)
        except Exception as e:
            logger.warning("[automations] 行动失败({}): {}", atype, e)
        self._exec_at(actions, index + 1, wait_ms, uid)

    # ── 行动实现 ────────────────────────────────────────────

    def _do_run(self, a: dict) -> None:
        cmd = str(a.get("p1") or "").strip()
        if not cmd:
            return
        subprocess.Popen(cmd, shell=True)
        logger.info("[automations] 运行: {}", cmd[:120])

    def _do_notify(self, a: dict) -> None:
        if self._provider is None:
            try:
                self._provider = self._api.notification.get_provider(
                    "com.kryon.automations", name="Kryon 自动化")
            except Exception as e:
                logger.warning("[automations] 注册通知失败: {}", e)
                return
        try:
            duration = max(0, int(float(a.get("p3") or 4000)))
            level = max(0, min(3, int(float(a.get("p4") or 0))))
            self._provider.push(level,
                                str(a.get("p1") or "自动化提醒"),
                                str(a.get("p2") or ""),
                                duration, True)
        except Exception as e:
            logger.warning("[automations] 通知失败: {}", e)

    def _do_set_flag(self, a: dict, uid: Optional[str]) -> None:
        name = str(a.get("p1") or "").strip()
        if not name:
            return
        value = str(a.get("p2") or "")
        if name not in self._flag_originals:
            self._flag_originals[name] = self._flags.get(name)
        if uid and uid in self._active:
            self._active[uid]["flags"].setdefault(name, self._flag_originals[name])
        self._flags[name] = value
        self.save()

    def _do_set_config(self, a: dict, uid: Optional[str]) -> None:
        key = str(a.get("p1") or "")
        if key not in CONFIG_KEYS:
            logger.warning("[automations] 未知配置键: {}", key)
            return
        value = coerce(a.get("p2"), CONFIG_KEYS[key])
        self._apply_config(key, value, uid=uid)

    def _apply_config(self, key: str, value: Any, uid: Optional[str] = None) -> None:
        configs = self._api.globalconfig.configs
        parts = key.split(".")
        obj = configs
        for part in parts[:-1]:
            obj = getattr(obj, part)
        if uid and uid in self._active:
            orig = getattr(obj, parts[-1])
            self._record(key, orig, uid)
        setattr(obj, parts[-1], value)
        logger.info("[automations] 设置 {} = {}", key, value)

    def _do_lock(self, a: dict, uid: Optional[str]) -> None:
        key = str(a.get("p1") or "")
        if key not in CONFIG_KEYS:
            logger.warning("[automations] 未知锁定键: {}", key)
            return
        unlock = str(a.get("p2") or "").strip().lower() in ("unlock", "解锁", "0", "false")
        if uid and uid in self._active and not unlock:
            if key not in self._active[uid]["locked"]:
                self._active[uid]["locked"].append(key)
        if unlock:
            self._api.globalconfig.unlock(key)
        else:
            self._api.globalconfig.lock(key)
        logger.info("[automations] {} 配置键 {}", "解锁" if unlock else "锁定", key)

    def _record(self, key: str, orig: Any, uid: str) -> None:
        rec = self._active.get(uid)
        if rec:
            rec.setdefault("keys", {})
            rec["keys"].setdefault(key, orig)

    # ── 恢复 ────────────────────────────────────────────────

    def _revert_scan(self) -> None:
        for uid, rec in list(self._active.items()):
            rule = rec["rule"]
            if rule.get("revert") and self._evaluate_ruleset(rule) is False:
                self._revert(uid)

    def _revert(self, uid: str) -> None:
        rec = self._active.pop(uid, None)
        if not rec:
            return
        configs = self._api.globalconfig.configs
        for key, orig in (rec.get("keys") or {}).items():
            try:
                obj = configs
                for part in key.split(".")[:-1]:
                    obj = getattr(obj, part)
                setattr(obj, key.split(".")[-1], orig)
                logger.info("[automations] 恢复 {} = {}", key, orig)
            except Exception as e:
                logger.warning("[automations] 恢复失败 {}: {}", key, e)
        for name, orig in (rec.get("flags") or {}).items():
            if orig is None:
                self._flags.pop(name, None)
            else:
                self._flags[name] = orig
        for key in (rec.get("locked") or []):
            try:
                self._api.globalconfig.unlock(key)
            except Exception:
                pass

    # ── 规则集求值 ──────────────────────────────────────────

    def _evaluate_ruleset(self, rule: dict) -> bool:
        rs = rule.get("ruleset") or {}
        if not rs.get("enabled"):
            return True
        rules = rs.get("rules") or []
        if not rules:
            return True
        results = [self._eval_rule(r) for r in rules]
        mode = rs.get("mode") or "all"
        satisfied = all(results) if mode == "all" else any(results)
        if rs.get("reversed"):
            satisfied = not satisfied
        return satisfied

    def _eval_rule(self, r: dict) -> bool:
        t = r.get("type")
        p1 = str(r.get("p1") or "")
        p2 = str(r.get("p2") or "")
        p3 = str(r.get("p3") or "")
        try:
            if t == R_ALWAYS_TRUE:
                v = True
            elif t == R_ALWAYS_FALSE:
                v = False
            elif t == R_TODAY_IS:
                v = self._today_is(p1)
            elif t == R_LATER_THAN:
                v = self._later_than(p1)
            elif t == R_CURRENT_SUBJECT:
                v = self._subject_match(self._api.runtime.current_subject, p1)
            elif t == R_NEXT_SUBJECT:
                v = self._subject_match(self._next_subject(), p1)
            elif t == R_PREV_SUBJECT:
                v = self._subject_match(self._prev_subject(), p1)
            elif t == R_CURRENT_STATUS:
                v = self._safe_status() == p1
            elif t == R_FOREGROUND_WINDOW:
                v = self._foreground_window(p1, p2, p3)
            elif t == R_FLAG_IS:
                v = self._flags.get(p1) == p2
            elif t == R_CURRENT_TEACHER:
                v = self._teacher_match(self._api.runtime.current_subject, p1)
            elif t == R_NEXT_TEACHER:
                v = self._teacher_match(self._next_subject(), p1)
            else:
                v = False
        except Exception:
            v = False
        return (not v) if r.get("reversed") else v

    @staticmethod
    def _today_is(p1: str) -> bool:
        now = datetime.datetime.now().isoweekday()
        spec = p1.strip().lower()
        if spec in ("weekend", "周末"):
            return now in (6, 7)
        if spec in ("weekday", "周内", "工作日"):
            return now in (1, 2, 3, 4, 5)
        if spec:
            return str(now) in re.split(r"[,，、\s]+", spec)
        return False

    @staticmethod
    def _later_than(p1: str) -> bool:
        m = re.match(r"^(\d{1,2}):(\d{2})$", p1.strip())
        if not m:
            return False
        now = datetime.datetime.now().time()
        return now >= datetime.time(int(m.group(1)), int(m.group(2)))

    @staticmethod
    def _subject_match(subject: Optional[Any], needle: str) -> bool:
        if not subject or not needle.strip():
            return False
        name = subject.get("name") if isinstance(subject, dict) else getattr(subject, "name", None)
        simplified = subject.get("simplifiedName") if isinstance(subject, dict) else getattr(subject, "simplifiedName", None)
        n = needle.strip()
        return n in (name or "") or n in (simplified or "")

    @staticmethod
    def _teacher_match(subject: Optional[Any], needle: str) -> bool:
        if not subject or not needle.strip():
            return False
        teacher = subject.get("teacher") if isinstance(subject, dict) else getattr(subject, "teacher", None)
        return needle.strip() in (teacher or "")

    def _next_subject(self) -> Optional[Any]:
        try:
            entries = self._api.runtime.next_entries or []
            subject_id = entries[0].get("subjectId") if entries else None
            return self._subject_by_id(subject_id)
        except Exception:
            return None

    def _prev_subject(self) -> Optional[Any]:
        try:
            entries = self._api.runtime.current_day_entries or []
            cur = self._api.runtime.current_entry or {}
            prev = None
            for e in entries:
                if e.get("id") == cur.get("id"):
                    break
                prev = e
            return self._subject_by_id(prev.get("subjectId")) if prev else None
        except Exception:
            return None

    def _subject_by_id(self, subject_id: Optional[str]) -> Optional[Any]:
        if not subject_id:
            return None
        try:
            schedule = self._api.schedule.get()
            for s in (schedule.subjects if schedule else []):
                sid = s.id if hasattr(s, "id") else s.get("id")
                if sid == subject_id:
                    return s
        except Exception:
            return None
        return None

    def _foreground_window(self, needle: str, mode: str, state: str) -> bool:
        try:
            import win32gui
            import win32con
            import ctypes
        except Exception:
            return False
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return False
            title = win32gui.GetWindowText(hwnd)
            proc = ""
            try:
                import win32process
                import psutil
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                proc = psutil.Process(pid).name()
            except Exception:
                pass
            if state in ("maximized", "最大化"):
                if not win32gui.GetWindowPlacement(hwnd)[1] == win32con.SW_MAXIMIZE:
                    return False
            if state in ("fullscreen", "全屏"):
                rect = win32gui.GetWindowRect(hwnd)
                sw = ctypes.windll.user32.GetSystemMetrics(0)
                sh = ctypes.windll.user32.GetSystemMetrics(1)
                if not (rect[0] <= 2 and rect[1] <= 2 and rect[2] >= sw - 2 and rect[3] >= sh - 2):
                    return False
            if not needle.strip():
                return True
            hay = f"{title} {proc}"
            n = needle.strip()
            return (n.lower() in hay.lower()) if mode in ("contains", "包含", "") else (n.lower() == hay.lower())
        except Exception:
            return False

    # ── 工具 ────────────────────────────────────────────────

    def _safe_status(self) -> str:
        try:
            return self._api.runtime.current_status or "free"
        except Exception:
            return "free"

    def app_started(self) -> None:
        QTimer.singleShot(1200, self._fire_app_start)

    def _fire_app_start(self) -> None:
        for rule in self._rules:
            if not rule.get("enabled"):
                continue
            if any(t.get("type") == T_APP_START for t in rule.get("triggers") or []):
                self._maybe_fire(rule, {"type": T_APP_START})

    def shutdown(self) -> None:
        try:
            self._tick_timer.stop()
        except Exception:
            pass

    # ── 清洗 ────────────────────────────────────────────────

    @staticmethod
    def _clean_rule(r: dict) -> dict:
        def fields(src: Optional[dict]) -> dict:
            src = src or {}
            return {"type": str(src.get("type") or ""),
                    "p1": str(src.get("p1") or ""),
                    "p2": str(src.get("p2") or ""),
                    "p3": str(src.get("p3") or ""),
                    "p4": str(src.get("p4") or ""),
                    "reversed": bool(src.get("reversed"))}

        triggers = [fields(t) for t in (r.get("triggers") or [])
                    if isinstance(t, dict) and t.get("type") in TRIGGER_TYPES]
        if not triggers:
            triggers = [{"type": T_TIME, "p1": "08:00", "p2": "", "p3": "", "p4": "", "reversed": False}]

        rs = r.get("ruleset") or {}
        rules = [fields(x) for x in (rs.get("rules") or [])
                 if isinstance(x, dict) and x.get("type") in RULE_TYPES]

        actions = [fields(a) for a in (r.get("actions") or [])
                   if isinstance(a, dict) and a.get("type") in ACTION_TYPES]
        if not actions:
            actions = [{"type": A_NOTIFY, "p1": "自动化提醒", "p2": "", "p3": "4000",
                        "p4": "0", "reversed": False}]

        return {
            "uid": str(r.get("uid") or uuid.uuid4().hex[:12]),
            "name": (str(r.get("name") or "").strip() or "未命名自动化")[:60],
            "enabled": bool(r.get("enabled", True)),
            "revert": bool(r.get("revert")),
            "triggers": triggers,
            "ruleset": {
                "enabled": bool(rs.get("enabled")),
                "mode": str(rs.get("mode") or "all"),
                "reversed": bool(rs.get("reversed")),
                "rules": rules,
            },
            "actions": actions,
        }
