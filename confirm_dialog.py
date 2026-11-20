# -*- coding: utf-8 -*-
"""确认 / 取消弹窗（RinUI 版）。

外观照搬主程序「重复打开 CW2」时那个提示窗（全屏透明 + RinUI Dialog + 底部两个整宽按钮），
并多一行「N 秒后自动…」的会话倒计时，让人一眼看出弹窗还有多久消失。

对引擎暴露的接口不变：
    init(app)                       在 on_load（GUI 线程）调一次
    show_confirm(...)               弹窗；on_result(bool) 回调
    close_confirm(result_ok=False)  外部关闭（插件卸载 / 新弹窗顶掉旧弹窗）
"""
from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

PLUGIN_DIR = Path(__file__).resolve().parent


class _Bridge(QObject):
    """QML → Python 的结果信号。"""

    result = Signal(bool)


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

    def present(self, title: str, body: str, ok_text: str, cancel_text: str,
                timeout_s: int, timeout_ok: bool) -> None:
        self.root.setProperty("headline", title)
        self.root.setProperty("bodyText", body)
        self.root.setProperty("okText", ok_text)
        self.root.setProperty("cancelText", cancel_text)
        self.root.setProperty("timeoutSeconds", int(timeout_s))
        self.root.setProperty("timeoutOk", bool(timeout_ok))
        nonce = int(self.root.property("showNonce") or 0) + 1
        self.root.setProperty("showNonce", nonce)

    def force_close(self, ok: bool) -> None:
        self.root.setProperty("forceOk", bool(ok))
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


def _on_result(ok: bool) -> None:
    global _callback
    cb = _callback
    _callback = None
    if cb is None:
        return
    logger.info("[confirm_dialog] 用户选择: {}", "确认" if ok else "取消")
    try:
        cb(bool(ok))
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


def show_confirm(title: str, body: str, ok_text: str, cancel_text: str,
                 timeout_s: int, timeout_ok: bool, on_result) -> None:
    """显示确认弹窗（任意线程可调）；已有旧弹窗时旧的按「取消」结算。"""

    def _run() -> None:
        global _callback
        window = _ensure_window()
        if window is None:
            try:
                on_result(False)                 # 弹不出来就按取消，别把链条挂死
            except Exception:                            # noqa: BLE001
                pass
            return
        if _callback is not None:
            try:
                _callback(False)
            except Exception:                            # noqa: BLE001
                pass
            _callback = None
        _callback = on_result
        window.present(title, body, ok_text, cancel_text, timeout_s, timeout_ok)
        logger.info("[confirm_dialog] 弹窗已显示: {}", title)

    _on_gui(_run)


def close_confirm(result_ok: bool = False) -> None:
    """外部要求关闭当前弹窗（如插件卸载）：按 result_ok 结算。"""
    def _run() -> None:
        if _window is None or _callback is None:
            return
        _window.force_close(bool(result_ok))

    _on_gui(_run)
