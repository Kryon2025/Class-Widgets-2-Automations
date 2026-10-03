# -*- coding: utf-8 -*-
"""系统通知：读 Windows 通知库（wpndatabase.db / appdb.dat）+ 发 toast。

零额外依赖：
    读 —— 标准库 sqlite3 + xml.etree，直接读 Windows 通知中心数据库；
    发 —— vendor 里的 winsdk（惰性导入、失败优雅降级，与 media.py 同一套做法）。

能力：
    触发「收到系统通知时」：应用名/内容 都按「包含」过滤，可空 = 任意。
    条件「系统通知…」：最近 N 秒内，应用名/内容 是否 包含/不包含 某值。
    动作「发系统通知」：弹一条 Windows toast（标题 + 内容）。
"""
from __future__ import annotations

import os
import sqlite3
import time
import xml.etree.ElementTree as ET

from loguru import logger

_DB_DIR = os.path.expandvars(r"%LocalAppData%\Microsoft\Windows\Notifications")
_FT_UNIX_OFFSET = 11644473600        # 1601-01-01 → 1970-01-01 的秒差

TOAST_APP_ID = "Kryon.Automations"

_last_arrival = None                 # 已见过的最大 ArrivalTime（FILETIME），用于「新通知」基线
_avail = None                        # 通知库是否可读（None=未知）
_cache = {"t": 0.0, "rows": []}      # recent() 缓存（1 秒内不重复开库）
_poll_cache = {"t": 0.0, "new": []}  # poll_new() 缓存（同一次 tick 内多次调用共享结果）
_CACHE_TTL = 1.0

_name_map = {"t": 0.0, "m": {}}      # AUMID/可执行名(小写) → 友好显示名（来自 app_index）


def _db_files() -> list:
    # Win10/多数 Win11 用 wpndatabase.db，部分新 Win11 用 appdb.dat，都试。
    return [os.path.join(_DB_DIR, n) for n in ("appdb.dat", "wpndatabase.db")]


def _open():
    for p in _db_files():
        if not os.path.exists(p):
            continue
        try:
            con = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=2)
            con.execute("PRAGMA query_only=1")
            return con
        except Exception as e:                       # noqa: BLE001
            logger.debug("[notify] 打开通知库失败 {}: {}", p, e)
    return None


def available() -> bool:
    global _avail
    if _avail is None:
        con = _open()
        _avail = con is not None
        if con:
            con.close()
    return _avail


def _texts(payload) -> list:
    if not payload:
        return []
    try:
        root = ET.fromstring(payload)
        return [t.text or "" for t in root.iter() if t.tag.rsplit("}", 1)[-1] == "text"]
    except Exception:                                # noqa: BLE001
        return []


def _query_recent(limit: int = 50) -> list:
    con = _open()
    if con is None:
        return []
    try:
        con.row_factory = sqlite3.Row
        handlers = {}
        try:
            for row in con.execute('SELECT "RecordId", "PrimaryId" FROM NotificationHandler'):
                handlers[row["RecordId"]] = row["PrimaryId"]
        except Exception:                            # noqa: BLE001
            pass
        try:
            cur = con.execute(
                'SELECT "HandlerId", "Payload", "ArrivalTime", "Type" '
                'FROM "Notification" ORDER BY "ArrivalTime" DESC LIMIT ?', (limit,))
        except Exception as e:                       # noqa: BLE001
            logger.debug("[notify] 查询通知失败: {}", e)
            return []
        rows = []
        for row in cur:
            texts = _texts(row["Payload"])
            if str(row["Type"] or "").lower() != "toast" and not texts:
                continue                             # 过滤 tile/raw 等无文本条目
            pid = str(handlers.get(row["HandlerId"], row["HandlerId"] or ""))
            rows.append({
                "app": pid,
                "app_name": _resolve_app(pid),
                "arrival": row["ArrivalTime"],
                "texts": texts,
            })
        return rows
    finally:
        con.close()


def recent(limit: int = 50) -> list:
    now = time.monotonic()
    if now - _cache["t"] < _CACHE_TTL:
        return _cache["rows"]
    _cache["rows"] = _query_recent(limit)
    _cache["t"] = now
    return _cache["rows"]


def poll_new() -> list:
    """上次刷新之后新到的通知（首次调用只校准基线，返回 []）。"""
    global _last_arrival
    now = time.monotonic()
    if now - _poll_cache["t"] < _CACHE_TTL:
        return _poll_cache["new"]
    rows = recent(50)
    new = []
    if rows:
        top = max(r["arrival"] or 0 for r in rows)
        if _last_arrival is None:
            _last_arrival = top                  # 首调：把现有历史当基线，不触发
        else:
            new = [r for r in rows if r["arrival"] and r["arrival"] > _last_arrival]
            _last_arrival = top
    _poll_cache["t"] = now
    _poll_cache["new"] = new
    return new


def _app_name_map() -> dict:
    """AUMID / 可执行名（小写）→ 友好显示名；来源是插件自己的应用列表（app_index）。

    这样下拉里选的「显示名」能对上通知库里的来源 ID：桌面应用是进程/名字，
    UWP 是 AUMID（如 Microsoft.ScreenSketch_8wekyb3d8bbwe!App）。
    """
    now = time.monotonic()
    if now - _name_map["t"] < 60.0 and _name_map["m"]:
        return _name_map["m"]
    m = {}
    try:
        import json

        import app_index
        raw = app_index.cached_apps_json()          # 只读缓存，绝不触发枚举
        if raw:
            for a in json.loads(raw):
                if not isinstance(a, dict):
                    continue
                name = str(a.get("name") or "").strip()
                target = str(a.get("target") or "").strip()
                if not name or not target:
                    continue
                if target.lower().startswith("shell:appsfolder\\"):
                    m[target[len("shell:AppsFolder\\"):].lower()] = name
                base = target.replace("/", "\\").rsplit("\\", 1)[-1].lower()
                if base.endswith(".lnk"):
                    base = base[:-4]
                if base:
                    m.setdefault(base, name)
    except Exception as e:                          # noqa: BLE001
        logger.debug("[notify] 读取应用名映射失败: {}", e)
    _name_map["t"] = now
    _name_map["m"] = m
    return m


def _resolve_app(pid: str) -> str:
    pid = str(pid or "")
    m = _app_name_map()
    if pid.lower() in m:
        return m[pid.lower()]
    base = pid.replace("/", "\\").rsplit("\\", 1)[-1].lower()
    if base.endswith(".exe"):
        base = base[:-4]
    return m.get(base, pid)


def _app_hit(r, needle: str) -> bool:
    """来源匹配：拿「显示名」和「原始来源 ID」都按「包含」比一次（不区分大小写）。"""
    n = str(needle or "").lower()
    return n in str(r.get("app") or "").lower() or n in str(r.get("app_name") or "").lower()


def _hit(r, app: str, text: str) -> bool:
    if app and not _app_hit(r, app):
        return False
    if text and text not in " ".join(r["texts"]):
        return False
    return True


def poll_match(app: str = "", text: str = "") -> bool:
    a = str(app or "").strip()
    t = str(text or "").strip()
    return any(_hit(r, a, t) for r in poll_new())


def rule_match(key: str, op: str, value: str, window: str = "60") -> bool:
    """规则条件：最近 window 秒内，应用名/内容 是否 包含/不包含 某值。"""
    k = str(key or "").strip()
    o = str(op or "").strip() or "=="
    v = str(value or "").strip()
    try:
        win = max(1, int(float(window or 60)))
    except (TypeError, ValueError):
        win = 60
    floor = int((time.time() + _FT_UNIX_OFFSET) * 10_000_000) - win * 10_000_000
    rows = [r for r in recent() if r["arrival"] and r["arrival"] >= floor]
    if k == "app":
        hit = any(_app_hit(r, v) for r in rows)
    else:
        hit = any(v in " ".join(r["texts"]) for r in rows)
    return hit if o not in ("!=", "<>", "≠", "不是") else (not hit)


# ── 发 toast（winsdk 惰性导入）───────────────────────────────
_toast = None


def _load_toast() -> bool:
    global _toast
    if _toast is not None:
        return True
    try:
        import deps
        deps.ensure_sys_path()
    except Exception:                                # noqa: BLE001
        pass
    try:
        from winsdk.windows.ui.notifications import ToastNotificationManager, ToastNotification
        from winsdk.windows.data.xml.dom import XmlDocument
        _toast = (ToastNotificationManager, ToastNotification, XmlDocument)
        logger.info("[notify] winsdk toast 导入成功 ✓")
        return True
    except Exception as e:                           # noqa: BLE001
        logger.debug("[notify] winsdk toast 尚未可用: {}", e)
        return False


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def send(title: str, body: str = "") -> bool:
    if not _load_toast():
        return False
    Mgr, Toast, Xml = _toast
    try:
        t = _esc(str(title or "通知"))
        b = _esc(str(body or ""))
        xml = Xml()
        xml.load_xml(
            '<toast><visual><binding template="ToastGeneric">'
            f'<text>{t}</text><text>{b}</text>'
            '</binding></visual></toast>')
        notifier = Mgr.create_toast_notifier(TOAST_APP_ID)
        if notifier:
            notifier.show(Toast(xml))
            return True
        return False
    except Exception as e:                           # noqa: BLE001
        logger.warning("[notify] 发通知失败: {}", e)
        return False
