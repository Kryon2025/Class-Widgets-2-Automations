# -*- coding: utf-8 -*-
"""SMTC（Windows 系统媒体控制）—— 走 vendor 地基里的 winrt 包。

能力：
    动作：播放/暂停 · 播放 · 暂停 · 上一首 · 下一首 · 停止
    条件：是否在播放 · 曲名 · 歌手
依赖 winrt-Windows.Media.Control（已随插件放进 vendor/，首次启动自动解包）。
"""
from __future__ import annotations

import asyncio
import time

from loguru import logger

_Manager = None
_IMPORT_ERR = None
_CACHE: dict = {}


def _load() -> bool:
    """延迟导入 winrt。

    必须在 deps.ensure() 之后才可能成功 —— 因为插件模块（automations→media）的顶层
    导入发生在 on_load 之前，那时 vendor 还没解包、sys.path 还没挂。所以这里做成
    "首次真正用到时才导入"，并且**失败不缓存**（deps 就绪后重试即可成功）。
    """
    global _Manager, _IMPORT_ERR
    if _Manager is not None:
        return True
    # 主程序加载完插件后会重置 sys.path（防插件污染），所以这里每次都要重新挂一次
    try:
        import deps
        deps.ensure_sys_path()
    except Exception:                                    # noqa: BLE001
        pass
    try:
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as M,
        )
        _Manager = M
        _IMPORT_ERR = None
        logger.info("[media] winrt 导入成功 ✓")
        return True
    except Exception as e:                               # noqa: BLE001
        _IMPORT_ERR = e
        logger.debug("[media] winrt 尚未可用: {}", e)
        _diag_once()
        return False


_DIAG_DONE = False


def _diag_once() -> None:
    """只在第一次失败时打一次详细诊断，方便定位（冻结环境 / sys.path / 文件是否在）。"""
    global _DIAG_DONE
    if _DIAG_DONE:
        return
    _DIAG_DONE = True
    try:
        import importlib
        import os
        import sys
        from pathlib import Path
        v = Path(__file__).resolve().parent / "vendor"
        logger.warning("[media] 诊断: frozen={} | vendor在sys.path={} | vendor/winrt={} | "
                       "winrt/__init__.py={} | find_spec={}",
                       getattr(sys, "frozen", False), str(v) in sys.path,
                       (v / "winrt").is_dir(), (v / "winrt" / "__init__.py").exists(),
                       _safe_find("winrt"))
    except Exception as e:                               # noqa: BLE001
        logger.warning("[media] 诊断本身失败: {}", e)


def _safe_find(name):
    try:
        import importlib.util
        return importlib.util.find_spec(name)
    except Exception as e:                               # noqa: BLE001
        return f"err:{e}"


def available() -> bool:
    return _load()


def _run(op):
    """winrt 的异步操作返回 _IAsyncOperation（非协程），必须先 await 再 asyncio.run。"""
    async def _await():
        return await op
    return asyncio.run(_await())


def _session():
    if not _load():
        return None
    try:
        mgr = _run(_Manager.request_async())
        return mgr.get_current_session() if mgr else None
    except Exception as e:                               # noqa: BLE001
        logger.debug("[media] 取会话失败: {}", e)
        return None


# ── 动作 ────────────────────────────────────────────────────
MEDIA_ACTIONS = ("toggle", "play", "pause", "prev", "next", "stop")
MEDIA_ACTION_LABELS = ("播放 / 暂停", "播放", "暂停", "上一首", "下一首", "停止")


def action(cmd: str) -> bool:
    s = _session()
    if s is None:
        logger.debug("[media] 没有可控的媒体会话")
        return False
    c = str(cmd or "").strip().lower()
    try:
        if c == "toggle":
            _run(s.try_toggle_play_pause_async())
        elif c == "play":
            _run(s.try_play_async())
        elif c == "pause":
            _run(s.try_pause_async())
        elif c == "prev":
            _run(s.try_skip_previous_async())
        elif c == "next":
            _run(s.try_skip_next_async())
        elif c == "stop":
            _run(s.try_stop_async())
        else:
            return False
    except Exception as e:                               # noqa: BLE001
        logger.warning("[media] 控制失败({}): {}", c, e)
        return False
    _CACHE.clear()
    logger.info("[media] 已执行: {}", c)
    return True


# ── 条件 ────────────────────────────────────────────────────
MEDIA_KEYS = ("playing", "title", "artist")
MEDIA_KEY_LABELS = ("是否在播放", "曲名", "歌手")


def info(ttl: float = 1.0) -> dict:
    """当前媒体信息（带 1 秒缓存 —— 规则每秒求值，不能每次都去问系统）。"""
    now = time.time()
    hit = _CACHE.get("info")
    if hit and now - hit[0] < ttl:
        return hit[1]
    r = {"playing": None, "title": "", "artist": ""}
    s = _session()
    if s is not None:
        try:
            pb = s.get_playback_info()
            st = getattr(pb, "playback_status", None)
            val = getattr(st, "value", st)
            r["playing"] = (int(val) == 4) if val is not None else None   # 4 = PLAYING
            props = _run(s.try_get_media_properties_async())
            if props is not None:
                r["title"] = str(props.title or "")
                r["artist"] = str(props.artist or "")
        except Exception as e:                           # noqa: BLE001
            logger.debug("[media] 读媒体信息失败: {}", e)
    _CACHE["info"] = (now, r)
    return r


def read_value(key: str):
    """给规则条件用：返回该键的当前值（读不到 None）。"""
    k = str(key or "").strip()
    if k not in MEDIA_KEYS:
        return None
    v = info().get(k)
    if k == "playing":
        return None if v is None else ("yes" if v else "no")
    return v


def rule_match(key: str, op: str, value: str) -> bool:
    cur = read_value(key)
    if cur is None:
        return False
    o = str(op or "").strip() or "=="
    if o in ("!=", "<>", "≠", "不是"):
        o = "!="
    v = str(value or "").strip()
    if cur in ("yes", "no"):                             # 播放状态是对/错
        want = v.lower() in ("yes", "true", "1", "是", "在播", "playing")
        return (cur == "yes") != want if o == "!=" else ((cur == "yes") == want)
    return cur != v if o == "!=" else (v in cur)         # 曲名/歌手按"包含"匹配更实用
