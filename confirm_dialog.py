# -*- coding: utf-8 -*-
"""确认 / 取消弹窗（RinUI 版，支持多个按钮 + 自定义按钮配色）。

外观照搬主程序「重复打开 CW2」时那个提示窗（全屏透明 + RinUI Dialog + 底部整宽按钮），
并多一行「N 秒后自动按「…」」的会话倒计时。

对引擎暴露的接口：
    init(app)                                  在 on_load（GUI 线程）调一次
    show_confirm(title, body, buttons, timeout_s, timeout_index, on_result)
        buttons: [{"text": ..., "bg": "#rrggbb"|"", "fg": "#rrggbb"|""}, ...]
        timeout_index: 超时自动按第几个按钮（0 起；-1 = 不自动）
        on_result(index): 0 起的按钮序号；-1 = 被强制关闭
    close_confirm(index=-1)                    外部关闭（卸载 / 新弹窗顶掉旧弹窗）
"""
from __future__ import annotations

import json
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

PLUGIN_DIR = Path(__file__).resolve().parent


class _Bridge(QObject):
    """QML → Python 的按钮序号。"""

    result = Signal(int)


_bridge: _Bridge | None = None
_app = None
_window: "ConfirmDialog | None" = None
_callback = None


def init(app=None) -> None:
    """在 GUI 线程调用一次；app 用来取主程序的信息图标。"""
    global _bridge, _app
    _app = app
    if _bridge is None:
        _bridge = _Bridge()
        logger.info("[confirm_dialog] GUI 桥已就绪")


class ConfirmDialog:
    """常驻一个 RinUI 窗口，每次弹窗改属性再 show，避免反复建窗口卡顿。"""

    def __init__(self, app=None):
        from RinUI import RinUIWindow

        self._window = RinUIWindow(shared_engine=False)
        engine = self._window.engine
        engine.rootContext().setContextProperty("ConfirmBridge", _bridge)

        icon = ""
        try:
            manager = getattr(app, "path_manager", None)
            if manager is not None:
                icon = manager.images("icons/cw2_info.png")
        except Exception as e:                            # noqa: BLE001
            logger.debug("[confirm_dialog] 取信息图标失败: {}", e)
        engine.rootContext().setContextProperty("ConfirmIconPath", icon)

        self._window.load(PLUGIN_DIR / "qml" / "confirm_dialog.qml")
        self.root = self._window.root_window
        try:
            self.root.setVisible(False)
        except Exception:                                 # noqa: BLE001
            pass
        logger.info("[confirm_dialog] 弹窗窗口已准备好")

    def present(self, title: str, body: str, buttons: list,
                timeout_s: int, timeout_index: int) -> None:
        self.root.setProperty("headline", title)
        self.root.setProperty("bodyText", body)
        self.root.setProperty("buttonsJson",
                              json.dumps(buttons or [], ensure_ascii=False))
        self.root.setProperty("timeoutSeconds", int(timeout_s))
        self.root.setProperty("timeoutIndex", int(timeout_index))
        nonce = int(self.root.property("showNonce") or 0) + 1
        self.root.setProperty("showNonce", nonce)

    def force_close(self, index: int) -> None:
        self.root.setProperty("forceIndex", int(index))
        nonce = int(self.root.property("forceNonce") or 0) + 1
        self.root.setProperty("forceNonce", nonce)


def _on_gui(fn) -> None:
    app = QApplication.instance()
    if app is None:
        logger.warning("[confirm_dialog] 没有 QApplication，无法显示")
        return
    try:
        fn()
    except Exception as e:                                # noqa: BLE001
        logger.warning("[confirm_dialog] 执行失败: {}", e)


def _on_result(index: int) -> None:
    global _callback
    cb = _callback
    _callback = None
    if cb is None:
        return
    logger.info("[confirm_dialog] 按钮选择: {}", index)
    try:
        cb(int(index))
    except Exception as e:                                # noqa: BLE001
        logger.warning("[confirm_dialog] 结果回调失败: {}", e)


def _ensure_window() -> "ConfirmDialog | None":
    global _window
    if _window is not None:
        return _window
    try:
        _window = ConfirmDialog(_app)
        if _bridge is not None:
            _bridge.result.connect(_on_result)
        return _window
    except Exception as e:                                # noqa: BLE001
        logger.warning("[confirm_dialog] 弹窗创建失败: {}", e)
        return None


def show_confirm(title: str, body: str, buttons: list,
                 timeout_s: int, timeout_index: int, on_result) -> None:
    """显示确认弹窗（任意线程可调）；已有旧弹窗时旧的按「-1」结算。"""

    def _run() -> None:
        global _callback
        window = _ensure_window()
        if window is None:
            try:
                on_result(-1)                    # 弹不出来就按关闭，别把链条挂死
            except Exception:                            # noqa: BLE001
                pass
            return
        if _callback is not None:
            try:
                _callback(-1)
            except Exception:                            # noqa: BLE001
                pass
            _callback = None
        _callback = on_result
        window.present(title, body, buttons, timeout_s, timeout_index)
        logger.info("[confirm_dialog] 弹窗已显示: {}（{} 个按钮）", title, len(buttons or []))

    _on_gui(_run)


def close_confirm(index: int = -1) -> None:
    """外部要求关闭当前弹窗（如插件卸载）：按 index 结算（-1 = 关闭）。"""
    def _run() -> None:
        if _window is None or _callback is None:
            return
        _window.force_close(int(index))

    _on_gui(_run)
