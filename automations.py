# -*- coding: utf-8 -*-
"""Kryon 自动化 —— 核心引擎。

实现「自动化」能力（触发器 + 规则集 + 行动 + 恢复），
并支持间隔触发、今天是/时间晚于/读标志、当前教师/下节教师、设标志等扩展。

模型（每条自动化 = 触发器中任一 + 规则集过滤 + 行动序列）：
    triggers[]  任意一个触发即可
    rulesets    规则集数组：每项 enabled / mode(all|any) / reversed / rules[]
    rulesetMode 多个规则集之间：all = 全部满足，any = 满足其一
    actions[]   顺序执行（可含 wait）
    revert      是否在逆事件或规则集不再满足时自动恢复

触发器 / 规则 / 行动类型见文件底部常量表（与 QML 顺序一致）。
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QObject, QTimer, Signal
from loguru import logger

import app_index
import day_status
import media
import notify
import win_settings

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
T_ALARM = "alarm"               # 闹钟（到点自己响铃）
T_SYS_CHANGE = "sys_change"       # 系统设置变化时（p1 键，p2 可选「变为」）
T_BOOT = "boot"                   # 开机后（p1 = 开机多少秒内算"刚开机"，默认 120）
T_NOTIF = "notif_new"             # 收到系统通知时（p1 应用名含，p2 内容含，均可空）
# 随机点名联动（扩展功能，需 com.rollcall 插件）：开始滚动 / 出结果后
T_ROLLCALL_START = "rollcall_start"
T_ROLLCALL_PICKED = "rollcall_picked"
TRIGGER_TYPES = (T_ALARM, T_TIME, T_INTERVAL, T_CLASS_START, T_CLASS_END, T_BREAK_START,
                 T_AFTER_SCHOOL, T_STATUS_CHANGE, T_BEFORE_CLASS, T_APP_START, T_SIGNAL,
                 T_SYS_CHANGE, T_BOOT, T_NOTIF, T_ROLLCALL_START, T_ROLLCALL_PICKED)

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
R_SYS_SETTING = "sys_setting"          # 系统设置：主题/电源/电池/网络（p1 键 p2 比较 p3 值）
R_MEDIA = "media"                      # 媒体状态：是否在播/曲名/歌手（p1 键 p2 比较 p3 值）
R_NOTIF = "notif"                      # 系统通知：最近是否收到匹配的通知（p1 键 p2 比较 p3 值 p4 秒）
# 随机点名：读它的配置项做判断（p1 = 配置项键，p2 = 期望值）
R_ROLLCALL_CONFIG = "rollcall_config"
RULE_TYPES = (R_ALWAYS_TRUE, R_ALWAYS_FALSE, R_TODAY_IS, R_LATER_THAN,
              R_CURRENT_SUBJECT, R_NEXT_SUBJECT, R_PREV_SUBJECT, R_CURRENT_STATUS,
              R_FOREGROUND_WINDOW, R_FLAG_IS, R_CURRENT_TEACHER, R_NEXT_TEACHER,
              R_SYS_SETTING, R_MEDIA, R_NOTIF, R_ROLLCALL_CONFIG)

# ── 行动类型（顺序 = QML 下拉顺序）────────────────────────────
A_RUN = "run"                     # 运行命令/程序/网址
A_NOTIFY = "notify"               # 显示提醒
A_WAIT = "wait"                   # 等待
A_BROADCAST = "broadcast"         # 广播信号
A_SET_FLAG = "set_flag"           # 设标志
A_SET_CONFIG = "set_config"       # 设置配置项（主题/锚点/层级/隐藏/迷你…）
A_LOCK = "lock"                   # 锁定配置项
A_RESTART = "restart"             # 重启主程序
A_LAUNCH = "launch_app"           # 打开应用（已安装应用 / UWP / 指定 exe）
A_CLOSE_APP = "close_app"         # 关闭应用（旧类型，加载时迁移到 app）
A_APP = "app"                     # 应用管理：p4=open/close，p1=目标
A_OPEN_SETTINGS = "open_settings" # 打开 Windows 系统设置页（ms-settings:）
A_SET_THEME = "set_theme"         # 切换 Windows 深/浅色主题（可恢复）
A_POWER = "power"                 # 电源：关机/重启/注销/睡眠/休眠（p1 模式）
A_VOLUME = "volume"               # 音量：增大/减小/静音/设为某值（p1 模式 p2 值）
A_MEDIA = "media"                 # 媒体控制：播放/暂停/上下首/停止（p1 命令）
A_SYS_NOTIFY = "sys_notify"       # 发系统通知（toast）：p1 标题 p2 内容
# 随机点名联动（扩展功能，需 com.rollcall 插件在场）
A_ROLLCALL_ROLL = "rollcall_roll"     # 触发点名：p1 = 人数(1~5)
A_ROLLCALL_SET = "rollcall_set"       # 设置随机点名配置项：p1 = 键 p2 = 值
A_ROLLCALL_CLOSE = "rollcall_close"   # 关闭点名结果窗口

# 随机点名插件的 id
ROLLCALL_PLUGIN_ID = "com.rollcall"

ACTION_TYPES = (A_RUN, A_APP, A_NOTIFY, A_WAIT, A_BROADCAST, A_SET_FLAG,
                A_SET_CONFIG, A_LOCK, A_RESTART, A_OPEN_SETTINGS, A_SET_THEME,
                A_POWER, A_VOLUME, A_MEDIA, A_SYS_NOTIFY,
                A_ROLLCALL_ROLL, A_ROLLCALL_SET, A_ROLLCALL_CLOSE)

# 闹钟「闹钟铃声」时按顺序找系统自带的声音文件
ALARM_SOUND_FILES = ("Alarm01.wav", "Alarm02.wav", "Alarm03.wav",
                     "Ring01.wav", "Windows Notify.wav")

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
REVERTIBLE_ACTIONS = (A_SET_CONFIG, A_LOCK, A_SET_FLAG, A_SET_THEME)


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


# 窗口层级别名：允许用户在「设置配置项 → 层级」里填中文或其他写法
LAYER_ALIASES: dict[str, str] = {
    "top": "top", "顶层": "top", "上层": "top", "最上层": "top", "上面": "top", "上": "top",
    "bottom": "bottom", "底层": "bottom", "下层": "bottom", "最下层": "bottom", "下面": "bottom", "下": "bottom",
    "normal": "normal", "普通": "normal", "正常": "normal", "中间": "normal", "默认": "normal",
}


def normalize_layer(value: Any) -> str:
    """把层级写法归一化为 top / bottom / normal；无法识别时原样返回小写值。"""
    s = str(value).strip().lower()
    return LAYER_ALIASES.get(s, s)


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
        self._notify_unregistered_warned = False
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
        self._ensure_rollcall_hook()
        try:
            for rule in self._rules:
                if not rule.get("enabled"):
                    continue
                for trig in rule.get("triggers") or []:
                    if self._check_trigger(rule, trig, now):
                        self._maybe_fire(rule, trig)
                        if trig.get("type") == T_ALARM:
                            self._ring_alarm(rule, trig)
                        break
        except Exception as e:
            logger.warning("[automations] tick 异常: {}", e)
        # 规则集持续监测：已执行的自动化在规则集变 false 时恢复
        self._revert_scan()

    # ── 触发器检测 ──────────────────────────────────────────

    # ── 随机点名信号挂接 ────────────────────────────────────

    def _ensure_rollcall_hook(self) -> None:
        """把点名插件的信号接到引擎上。插件晚到或重装时自动重挂。"""
        rc = self._rollcall()
        if rc is None:
            self._rc_hooked = None
            return
        if getattr(self, "_rc_hooked", None) is rc:
            return
        try:
            rc.rollRequested.connect(self._on_rollcall_start)
            rc.picked.connect(self._on_rollcall_picked)
        except Exception as e:
            logger.warning("[automations] 挂接随机点名信号失败: {}", e)
            return
        self._rc_hooked = rc
        logger.info("[automations] 已挂接随机点名信号")

    def _on_rollcall_start(self, _count=None) -> None:
        self._rc_start_seq = getattr(self, "_rc_start_seq", 0) + 1

    def _on_rollcall_picked(self, _names=None) -> None:
        self._rc_picked_seq = getattr(self, "_rc_picked_seq", 0) + 1

    def _check_trigger(self, rule: dict, trig: dict, now: datetime.datetime) -> bool:
        t = trig.get("type")
        if t in (T_TIME, T_ALARM):
            m = re.match(r"^(\d{1,2}):(\d{2})$", str(trig.get("p1") or "").strip())
            if not m:
                return False
            if (int(m.group(1)), int(m.group(2))) != (now.hour, now.minute):
                return False
            days = str(trig.get("p2") or "").strip()
            if days and str(now.isoweekday()) not in re.split(r"[,，、\s]+", days):
                return False
            if trig.get("p4") == "1" and not self._has_class_today():
                return False
            fp = f"{now.strftime('%Y%m%d')}-{trig.get('p1')}-{days}"
            if trig.get("_fp") == fp:
                return False
            trig["_fp"] = fp
            return True
        if t == T_ROLLCALL_START:
            seq = getattr(self, "_rc_start_seq", 0)
            if seq and trig.get("_rc_seq") != seq:
                trig["_rc_seq"] = seq
                return True
            return False
        if t == T_ROLLCALL_PICKED:
            seq = getattr(self, "_rc_picked_seq", 0)
            if seq and trig.get("_rcp_seq") != seq:
                trig["_rcp_seq"] = seq
                return True
            return False
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
        if t == T_BOOT:
            # 开机后：本次开机的 boot_id 与上次触发过的不一样，且开机时长在窗口内
            bid = win_settings.boot_id()
            if bid and getattr(self, "_boot_fired", None) != bid:
                win_secs = max(1, int(float(trig.get("p1") or 120)))
                up = win_settings.uptime_seconds()
                if 0 <= up <= win_secs:
                    self._boot_fired = bid
                    return True
            return False
        if t == T_SYS_CHANGE:
            key = str(trig.get("p1") or "").strip()
            if not key:
                return False
            cur = win_settings.read_setting(key)
            prev = self._sys_prev.get(key)
            self._sys_prev[key] = cur
            if prev is None or cur == prev:
                return False
            want = str(trig.get("p2") or "").strip()
            return (cur == want) if want else True
        if t == T_NOTIF:
            return notify.poll_match(str(trig.get("p1") or ""), str(trig.get("p2") or ""))
        return False

    def _has_class_today(self) -> bool:
        """今天课表里有没有「课程」条目。

        主程序的课表本身已经处理过调休（core/schedule/service.py），
        所以法定假日、调休上课日都会自动算对。
        """
        for entry in self._day_entries():
            if str(entry.get("type") or "") == "class":
                return True
        return False

    def _ring_alarm(self, rule: dict, trig: dict) -> None:
        """闹钟到点：弹一条系统级通知（标题 = 自动化名），再异步响铃。"""
        title = str(rule.get("name") or "闹钟")
        when = str(trig.get("p1") or "")
        try:
            self._do_notify({"p1": title, "p2": f"闹钟时间到（{when}）",
                             "p3": "10000", "p4": "3"})
        except Exception as e:  # noqa: BLE001
            logger.warning("[automations] 闹钟通知失败: {}", e)
        self._play_sound(str(trig.get("p3") or ""))

    def _play_sound(self, kind: str) -> None:
        """异步播放铃音，绝不阻塞图形线程。

        kind："" / "default" = 系统提示音；"exclamation" / "question" = 另外两种系统音；
        "alarm" = 系统自带闹钟声；其余视为自定义 .wav 路径。
        """
        try:
            import winsound
        except Exception:  # noqa: BLE001
            logger.debug("[automations] 非 Windows 环境，跳过铃声")
            return
        preset = (kind or "").strip()
        try:
            if preset in ("", "default", "系统提示音"):
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
                return
            if preset in ("exclamation", "警告音"):
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                return
            if preset in ("question", "询问音"):
                winsound.MessageBeep(winsound.MB_ICONQUESTION)
                return
            path = preset
            if preset in ("alarm", "闹钟铃声"):
                media = Path(os.environ.get("WINDIR") or r"C:\Windows") / "Media"
                path = ""
                for name in ALARM_SOUND_FILES:
                    if (media / name).exists():
                        path = str(media / name)
                        break
            if path and Path(path).exists():
                winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception as e:  # noqa: BLE001
            logger.warning("[automations] 响铃失败({}): {}", kind, e)

    def _next_entry(self) -> Optional[dict]:
        try:
            entries = self._api.runtime.next_entries or []
            return entries[0] if entries else None
        except Exception:
            return None

    # ── 课程事件（statusChanged 信号）────────────────────────

    def on_status_changed(self, status: str) -> None:
        host = status or ""
        # 状态一律以主程序为准（free = 空闲，即「放学后」）；主程序没给状态时才按课表推算
        now = self._effective_status(host)
        prev = self._prev_status
        self._prev_status = now

        def fire(ttype: str) -> None:
            for rule in self._rules:
                if not rule.get("enabled"):
                    continue
                if any(tr.get("type") == ttype for tr in (rule.get("triggers") or [])):
                    self._maybe_fire(rule, {"type": ttype})

        was_class = prev in ("class", "activity")
        is_class = host in ("class", "activity")

        if T_STATUS_CHANGE in (t.get("type") for r in self._rules for t in r.get("triggers") or []):
            fire(T_STATUS_CHANGE)
        if not was_class and is_class:
            fire(T_CLASS_START)
        elif was_class and not is_class:
            fire(T_CLASS_END)
        if host == "break":
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
            if atype == A_APP:
                if str(action.get("p4") or "") == "close":
                    self._do_close_app(action)
                else:
                    self._do_launch(action)
            elif atype == A_OPEN_SETTINGS:
                self._do_open_settings(action)
            elif atype == A_SET_THEME:
                self._do_set_theme(action, uid)
            elif atype == A_POWER:
                win_settings.power_action(str(action.get("p1") or ""))
            elif atype == A_VOLUME:
                win_settings.volume_action(str(action.get("p1") or ""),
                                           str(action.get("p2") or ""))
            elif atype == A_MEDIA:
                media.action(str(action.get("p1") or ""))
            elif atype == A_SYS_NOTIFY:
                notify.send(str(action.get("p1") or ""), str(action.get("p2") or ""))
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
            elif atype == A_ROLLCALL_ROLL:
                self._do_rollcall_roll(action)
            elif atype == A_ROLLCALL_SET:
                self._do_rollcall_set(action)
            elif atype == A_ROLLCALL_CLOSE:
                self._do_rollcall_close(action)
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

    def _do_close_app(self, a: dict) -> None:
        """关闭应用：按进程名结束（taskkill /IM <名字> /F）。

        p1 可以是完整 .exe 路径，也可以只写进程名（chrome.exe / chrome）。
        用 Popen 发出去就返回，不等待、不阻塞图形线程。
        说明：UWP/商店应用没有独立 exe，按进程名关不掉。
        """
        target = str(a.get("p1") or "").strip()
        if not target:
            return
        if target.lower().startswith("shell:"):
            logger.warning("[automations] 关闭应用：{} 是 UWP/商店应用，没有独立进程名，关不掉", target)
            return
        name = target.replace("/", "\\").rsplit("\\", 1)[-1].strip()
        if name.lower().endswith(".lnk"):
            name = name[:-4]                      # 开始菜单快捷方式：拿它的名字当进程名
        if not name.lower().endswith(".exe"):
            name += ".exe"
        try:
            subprocess.Popen(["taskkill", "/IM", name, "/F"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info("[automations] 关闭应用: {}", name)
        except Exception as e:  # noqa: BLE001
            logger.warning("[automations] 关闭应用失败({}): {}", name, e)

    def _do_launch(self, a: dict) -> None:
        """打开应用：p1=目标（.lnk / shell:AppsFolder… / .exe / 网址），p2=参数，p3=工作目录。"""
        app_index.launch(str(a.get("p1") or ""), str(a.get("p2") or ""), str(a.get("p3") or ""))

    def _do_open_settings(self, a: dict) -> None:
        """打开 Windows 系统设置页：p1=页 id（如 colors / display / bluetooth）。"""
        win_settings.open_page(str(a.get("p1") or ""))

    def _do_set_theme(self, a: dict, uid: Optional[str]) -> None:
        """切换 Windows 深/浅色主题：p1=模式（light/dark/toggle），p2=范围（both/apps/system）。

        可恢复：把切换前的原始值记进 rec["win"]["theme"]，_revert 时用 win_settings 写回。
        """
        orig = win_settings.set_theme(str(a.get("p1") or ""), str(a.get("p2") or "both"))
        if orig is None:
            return
        if uid and uid in self._active:
            rec = self._active[uid]
            rec.setdefault("win", {}).setdefault("theme", orig)

    def set_notification_provider(self, provider) -> None:
        """接收插件在 on_load 里注册好的通知 provider。

        必须在插件上下文内注册（主程序 components.py:107 会拒绝上下文外的注册），
        所以注册放在 on_load，引擎只负责持有句柄并推送。
        """
        self._provider = provider
        self._notify_unregistered_warned = False

    def _do_notify(self, a: dict) -> None:
        """弹一条灵动通知（用 on_load 注册好的 provider，不再现场注册）。"""
        if self._provider is None:
            if not self._notify_unregistered_warned:
                self._notify_unregistered_warned = True
                logger.warning(
                    "[automations] 通知 provider 未注册，已跳过这条提醒。"
                    "（原因通常是插件 on_load 里 register_provider 失败）")
            return
        try:
            duration = max(0, int(float(a.get("p3") or 4000)))
            level = max(0, min(3, int(float(a.get("p4") or 0))))
            # 用关键字参数：参数名与 com.rinlit.countdowndays 里已在用的写法一致
            self._provider.push(
                level=level,
                title=str(a.get("p1") or "自动化提醒"),
                message=str(a.get("p2") or ""),
                duration=duration,
                closable=True,
            )
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
        raw = a.get("p2")
        if key == "preferences.widgets_layer":
            raw = normalize_layer(raw)
        value = coerce(raw, CONFIG_KEYS[key])
        self._apply_config(key, value, uid=uid)

    @staticmethod
    def _same_value(value: Any, current: Any) -> bool:
        """判断目标值与现值是否已经一致（避免重复写盘、重复通知主程序）。"""
        try:
            if isinstance(value, bool) or isinstance(current, bool):
                return bool(value) == bool(current)
            if isinstance(value, (int, float)) and isinstance(current, (int, float)):
                return float(value) == float(current)
            return str(value) == str(current)
        except Exception:  # noqa: BLE001
            return False

    def _apply_config(self, key: str, value: Any, uid: Optional[str] = None) -> None:
        configs = self._api.globalconfig.configs
        parts = key.split(".")
        obj = configs
        for part in parts[:-1]:
            obj = getattr(obj, part)
        current = getattr(obj, parts[-1], None)
        if self._same_value(value, current):
            # 值没变就什么都不做：不 setattr、不落盘、不通知主程序。
            # 否则规则集反复满足时会把主程序拖进「每秒重应用一次」。
            return
        if uid and uid in self._active:
            self._record(key, current, uid)
        setattr(obj, parts[-1], value)
        # 必须落盘并通知主程序，否则层级/锚点/偏移这类窗口属性不会真正生效
        self._commit_config()
        logger.info("[automations] 设置 {} = {}", key, value)

    # 系统设置「上次值」—— 供 T_SYS_CHANGE 比较变化（放在类上，不动 __init__）
    _sys_prev: dict = {}
    _boot_fired = None

    # 延后合并保存用的状态（放在类上，不需要动 __init__）
    _config_dirty = False
    _flush_pending = False

    def _commit_config(self) -> None:
        """请求保存配置改动（不在这里同步调用宿主的 save()）。

        为什么绕这一下：本方法会在规则动作回调（状态信号 / QML 槽）里被调用，
        而宿主 save() 会立刻写盘并让主程序重新应用整套配置（重建窗口属性、层级、
        锚点、迷你模式等）。在回调里同步做这件事属于**重入**，是这类
        「Qt6Qml.dll + 0xc0000005 + 固定偏移」崩溃的典型成因。

        所以改成：只置脏标记，等当前回调跑完、回到事件循环后再合并保存一次。
        同一批改动只落盘一次，写入次数反而更少。
        """
        self._config_dirty = True
        if self._flush_pending:
            return
        self._flush_pending = True
        try:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(150, self._flush_config)
        except Exception:  # noqa: BLE001
            # 没有 Qt 可用时退回同步，至少保证功能不丢
            self._flush_pending = False
            self._flush_config()

    def _flush_config(self) -> None:
        self._flush_pending = False
        if not self._config_dirty:
            return
        self._config_dirty = False
        saved = False
        for attr in ("config", "globalconfig"):
            target = getattr(self._api, attr, None)
            save = getattr(target, "save", None)
            if callable(save):
                try:
                    save()
                    saved = True
                except Exception as e:
                    logger.warning("[automations] 保存全局配置失败({}): {}", attr, e)
        if saved:
            logger.info("[automations] 配置改动已合并保存（延后到事件循环，避免重入）")
        else:
            logger.warning("[automations] 未找到可用的配置保存接口，改动可能不会立即生效")

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
        # 恢复同样要落盘，否则层级等窗口属性不会还原
        self._commit_config()
        for name, orig in (rec.get("flags") or {}).items():
            if orig is None:
                self._flags.pop(name, None)
            else:
                self._flags[name] = orig
        # 系统设置类（第②片起）：主题单独还原
        theme = (rec.get("win") or {}).get("theme")
        if theme:
            win_settings.restore_theme(theme)
        for key in (rec.get("locked") or []):
            try:
                self._api.globalconfig.unlock(key)
            except Exception:
                pass

    # ── 规则集求值 ──────────────────────────────────────────

    @staticmethod
    def _ruleset_list(rule: dict) -> list:
        """取出这条自动化的所有规则集；兼容只写了单个 ruleset 的旧数据。"""
        group = rule.get("rulesets")
        if isinstance(group, list) and group:
            return [rs for rs in group if isinstance(rs, dict)]
        one = rule.get("ruleset")
        return [one] if isinstance(one, dict) else []

    def _one_ruleset_ok(self, rs: dict) -> bool:
        """单个规则集内部：按自己的 mode / reversed 判断。"""
        rules = rs.get("rules") or []
        if not rules:
            return True
        results = [self._eval_rule(r) for r in rules]
        mode = rs.get("mode") or "all"
        satisfied = all(results) if mode == "all" else any(results)
        if rs.get("reversed"):
            satisfied = not satisfied
        return satisfied

    def _evaluate_ruleset(self, rule: dict) -> bool:
        """规则集整体是否满足。

        每个规则集内部按自己的「全部满足 / 任一满足」判断；
        多个规则集之间按 rulesetMode：all = 全部满足，any = 满足其一。
        未启用的规则集不参与；一个启用的都没有时不过滤（保持原语义）。
        """
        enabled = [rs for rs in self._ruleset_list(rule) if rs.get("enabled")]
        if not enabled:
            return True
        checks = [self._one_ruleset_ok(rs) for rs in enabled]
        mode = str(rule.get("rulesetMode") or "all").lower()
        return any(checks) if mode in ("any", "or") else all(checks)

    # ── 随机点名（com.rollcall）桥接 ─────────────────────────
    # 随机点名配置项 → 插件上的 setter 槽名（只含随机点名本身，不含 SecRandom）
    ROLLCALL_SETTERS = {
        "luck_enabled": "setLuckEnabled",
        "no_repeat": "setNoRepeat",
        "animation_seconds": "setAnimationSeconds",
        "notify_duration": "setNotifyDuration",
        "window_visible": "setWindowVisible",
        "float_mode": "setFloatMode",
        "click_hide": "setClickHide",
        "button_width": "setButtonWidth",
        "button_height": "setButtonHeight",
        "mode": "setMode",
    }
    ROLLCALL_BOOL_KEYS = ("luck_enabled", "no_repeat", "window_visible",
                          "float_mode", "click_hide")

    def _rollcall(self):
        """取随机点名插件实例。同进程直接拿对象；未装/未启用则返回 None。"""
        try:
            pm = getattr(self._api._app, "plugin_manager", None)
            plugins = getattr(pm, "_plugins", None)
            if plugins:
                return plugins.get(ROLLCALL_PLUGIN_ID)
        except Exception:
            pass
        return None

    @staticmethod
    def _as_bool(raw) -> bool:
        return str(raw).strip().lower() in ("1", "true", "on", "yes", "是", "开", "开启")

    def _do_rollcall_roll(self, a: dict) -> None:
        rc = self._rollcall()
        if rc is None:
            logger.warning("[automations] 随机点名插件不可用，跳过触发点名")
            return
        try:
            n = int(float(str(a.get("p1") or "1")))
        except Exception:
            n = 1
        n = max(1, min(5, n))
        rc.requestRoll(n)
        logger.info("[automations] 触发随机点名 {} 人", n)

    def _do_rollcall_set(self, a: dict) -> None:
        rc = self._rollcall()
        if rc is None:
            logger.warning("[automations] 随机点名插件不可用，跳过配置修改")
            return
        key = str(a.get("p1") or "")
        slot = self.ROLLCALL_SETTERS.get(key)
        if not slot:
            logger.warning("[automations] 未知的随机点名配置项: {}", key)
            return
        fn = getattr(rc, slot, None)
        if not callable(fn):
            logger.warning("[automations] 随机点名插件缺少 {}（版本不匹配？）", slot)
            return
        raw = a.get("p2")
        if key in self.ROLLCALL_BOOL_KEYS:
            value = self._as_bool(raw)
        else:
            try:
                value = int(float(str(raw)))
            except Exception:
                value = str(raw or "")
        fn(value)
        logger.info("[automations] 设置随机点名 {} = {}", key, value)

    def _do_rollcall_close(self, a: dict) -> None:
        rc = self._rollcall()
        if rc is None:
            return
        fn = getattr(rc, "closeResult", None)
        if callable(fn):
            fn()
            logger.info("[automations] 关闭点名结果窗口")
        else:
            logger.warning("[automations] 随机点名插件缺少 closeResult（版本不匹配？）")

    def _rollcall_cfg_is(self, key: str, expect: str) -> bool:
        """随机点名配置项是否等于期望值（按字符串比较，忽略大小写）。"""
        rc = self._rollcall()
        if rc is None or not key:
            return False
        try:
            cfg = rc.getConfig()
        except Exception:
            return False
        if not isinstance(cfg, dict) or key not in cfg:
            return False
        actual = cfg.get(key)
        if isinstance(actual, bool):
            actual = "true" if actual else "false"
        return str(actual).strip().lower() == str(expect).strip().lower()

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
            elif t == R_SYS_SETTING:
                v = win_settings.rule_match(p1, p2, p3)
            elif t == R_MEDIA:
                v = media.rule_match(p1, p2, p3)
            elif t == R_NOTIF:
                v = notify.rule_match(p1, p2, p3, str(r.get("p4") or "60"))
            elif t == R_ROLLCALL_CONFIG:
                v = self._rollcall_cfg_is(p1, p2)
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
        """当前时间状态：以主程序为准（拿不到时才按课表推算）。"""
        try:
            host = self._api.runtime.current_status or day_status.HOST_FREE
        except Exception:
            host = day_status.HOST_FREE
        return self._effective_status(host)

    @staticmethod
    def _now_minutes() -> int:
        now = datetime.datetime.now()
        return now.hour * 60 + now.minute

    def _day_entries(self) -> list:
        """当天全部课程条目（取不到就返回空列表）。"""
        try:
            entries = self._api.runtime.current_day_entries or []
        except Exception:
            return []
        return [e for e in entries if isinstance(e, dict)]

    def _effective_status(self, host_status: str) -> str:
        """把主程序状态换算成插件视角的状态（默认原样沿用主程序）。"""
        try:
            return day_status.effective_status(
                host_status, self._day_entries(), self._now_minutes())
        except Exception as e:
            logger.debug("[automations] 放学判定失败，沿用主程序状态: {}", e)
            return str(host_status or day_status.HOST_FREE)

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

        def migrate_action(a: dict) -> dict:
            t = str(a.get("type") or "")
            if t == "launch_app":
                a = dict(a); a["type"] = "app"; a["p4"] = "open"
            elif t == "close_app":
                a = dict(a); a["type"] = "app"; a["p4"] = "close"
            return a

        triggers = [fields(t) for t in (r.get("triggers") or [])
                    if isinstance(t, dict) and t.get("type") in TRIGGER_TYPES]
        if not triggers:
            triggers = [{"type": T_TIME, "p1": "08:00", "p2": "", "p3": "", "p4": "", "reversed": False}]

        group = r.get("rulesets")
        if not isinstance(group, list) or not group:
            group = [r.get("ruleset") or {}]
        rulesets = []
        for rs in group:
            if not isinstance(rs, dict):
                continue
            rulesets.append({
                "enabled": bool(rs.get("enabled")),
                "mode": str(rs.get("mode") or "all"),
                "reversed": bool(rs.get("reversed")),
                "rules": [fields(x) for x in (rs.get("rules") or [])
                          if isinstance(x, dict) and x.get("type") in RULE_TYPES],
            })
        if not rulesets:
            rulesets = [{"enabled": False, "mode": "all", "reversed": False, "rules": []}]

        actions = [fields(migrate_action(a)) for a in (r.get("actions") or [])
                   if isinstance(a, dict) and migrate_action(a).get("type") in ACTION_TYPES]
        if not actions:
            actions = [{"type": A_NOTIFY, "p1": "自动化提醒", "p2": "", "p3": "4000",
                        "p4": "0", "reversed": False}]

        return {
            "uid": str(r.get("uid") or uuid.uuid4().hex[:12]),
            "name": (str(r.get("name") or "").strip() or "未命名自动化")[:60],
            "description": str(r.get("description") or "").strip()[:120],
            "enabled": bool(r.get("enabled", True)),
            "revert": bool(r.get("revert")),
            "triggers": triggers,
            "rulesets": rulesets,
            "rulesetMode": str(r.get("rulesetMode") or "all"),
            "actions": actions,
        }
