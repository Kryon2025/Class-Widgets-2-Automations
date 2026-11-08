# -*- coding: utf-8 -*-
"""确认 / 取消弹窗：给自动化行动链提供一个「等人拍板」的停靠点。

典型用法（眼保健操）：
    定时触发 → confirm 弹窗「眼操时间到了，切息屏吗？」
        点确认（或超时按 timeout_ok 处理）→ 继续执行后面的行动（切息屏…）
        点取消（或超时按取消）→ 跳过剩余行动，安静收场

设计要点：
    - 纯 QWidget，不依赖宿主 QML，仿 scroll_text 的信号桥模式；
    - 无边框、置顶、不出现在任务栏 / Alt+Tab（WS_EX_TOOLWINDOW）；
    - 屏幕中上方停靠（不挡讲台大屏正中的课程展示内容）；
    - 超时倒计时显示在提示文字里，到点按 timeout_ok 自动结算；
    - 同一时刻只允许一个弹窗：新的来时旧的按「取消」结算。

线程：窗口必须在 GUI 线程创建。init() 在插件 on_load（GUI 线程）调用；
其它线程调 show_confirm() / close_confirm() 会安全投递到 GUI 线程。
"""
from __future__ import annotations

import ctypes

from loguru import logger
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout, QWidget)

# 让窗口不出现在任务栏 / Alt+Tab（Windows 扩展样式）
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080


def _hide_from_taskbar(widget: QWidget) -> None:
    try:
        import sys
        if sys.platform != "win32":
            return
        hwnd = int(widget.winId())
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TOOLWINDOW)
    except Exception as e:                                   # noqa: BLE001
        logger.warning("[confirm_dialog] 隐藏任务栏图标失败: {}", e)


class _Bridge(QObject):
    """跨线程把调用丢回 GUI 线程。"""

    invoke = Signal(object)


_bridge: _Bridge | None = None
_window: "_ConfirmWindow | None" = None


def init() -> None:
    """在 GUI 线程调用一次，建立信号桥。"""
    global _bridge
    if _bridge is None:
        _bridge = _Bridge()
        _bridge.invoke.connect(lambda fn: _safe(fn))
        logger.info("[confirm_dialog] GUI 桥已就绪")


def _safe(fn):
    try:
        fn()
    except Exception as e:                                   # noqa: BLE001
        logger.warning("[confirm_dialog] 执行失败: {}", e)


def _on_gui(fn) -> None:
    app = QApplication.instance()
    if app is None:
        logger.warning("[confirm_dialog] 没有 QApplication，无法显示")
        return
    if _bridge is None or QApplication.instance().thread() == _bridge.thread():
        try:
            fn()
        except Exception as e:                               # noqa: BLE001
            logger.warning("[confirm_dialog] 执行失败: {}", e)
        return
    _bridge.invoke.emit(fn)


class _ConfirmWindow(QWidget):
    """置顶小弹窗：标题 + 正文 + 确认/取消 + 超时倒计时。"""

    def __init__(self, title: str, body: str, ok_text: str, cancel_text: str,
                 timeout_s: int, timeout_ok: bool,
                 on_result) -> None:                         # on_result(bool)
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Dialog)
        self._on_result = on_result
        self._timeout_ok = timeout_ok
        self._remain = max(0, int(timeout_s))
        self._settled = False

        self.setWindowTitle(title)
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setStyleSheet(
            "QWidget{background:#10151d;}"
            "QLabel{color:#ffffff; background:transparent;}"
            "QPushButton{"
            " background:#262626; color:#ffffff; border:1px solid #4a4a4a;"
            " border-radius:8px; padding:10px 26px; font-size:15px;}"
            "QPushButton:hover{border-color:#6f6f6f; background:#2e2e2e;}"
            "QPushButton:pressed{background:#3a3a3a;}"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 20)
        lay.setSpacing(10)

        t = QLabel(title)
        f = QFont()
        f.setPointSize(14)
        f.setBold(True)
        t.setFont(f)
        lay.addWidget(t)

        if body:
            b = QLabel(body)
            b.setWordWrap(True)
            b.setStyleSheet("QLabel{color:#c9d1d9;}")
            lay.addWidget(b)

        self._timer_label = QLabel("")
        self._timer_label.setStyleSheet("QLabel{color:#8b949e; font-size:12px;}")
        lay.addWidget(self._timer_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch(1)
        if cancel_text:
            cb = QPushButton(cancel_text)
            cb.clicked.connect(lambda: self._settle(False))
            btn_row.addWidget(cb)
        ok = QPushButton(ok_text)
        ok.setStyleSheet(
            "QPushButton{background:#2f7cf6; border-color:#2f7cf6;}"
            "QPushButton:hover{background:#3c88ff; border-color:#3c88ff;}"
            "QPushButton:pressed{background:#2669cc;}"
        )
        ok.clicked.connect(lambda: self._settle(True))
        btn_row.addWidget(ok)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)

        self._update_timer_label()
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setInterval(1000)
        self._timeout_timer.timeout.connect(self._tick)
        if self._remain > 0:
            self._timeout_timer.start()

    # ── 布局定位 ──
    def showEvent(self, event) -> None:                      # noqa: N802
        super().showEvent(event)
        _hide_from_taskbar(self)
        screen = self.screen() or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        self.adjustSize()
        w = max(self.width(), 380)
        self.resize(w, self.height())
        self.move(geo.center().x() - w // 2,
                  geo.top() + max(48, int(geo.height() * 0.12)))
        self.raise_()
        self.activateWindow()

    # ── 超时 ──
    def _tick(self) -> None:
        if self._settled:
            return
        self._remain -= 1
        self._update_timer_label()
        if self._remain <= 0:
            logger.info("[confirm_dialog] 超时，按「{}」处理",
                        "确认" if self._timeout_ok else "取消")
            self._settle(self._timeout_ok)

    def _update_timer_label(self) -> None:
        if self._remain > 0:
            act = "确认" if self._timeout_ok else "取消"
            self._timer_label.setText(f"{self._remain} 秒后自动「{act}」")
        else:
            self._timer_label.setText("")

    # ── 结算（幂等）──
    def _settle(self, ok: bool) -> None:
        if self._settled:
            return
        self._settled = True
        try:
            self._timeout_timer.stop()
        except Exception:                                    # noqa: BLE001
            pass
        self.close()
        logger.info("[confirm_dialog] 用户选择: {}", "确认" if ok else "取消")
        try:
            self._on_result(ok)
        except Exception as e:                               # noqa: BLE001
            logger.warning("[confirm_dialog] 结果回调失败: {}", e)

    def force_cancel(self) -> None:
        """外部强拆（新弹窗来了 / 插件卸载）：按取消结算。"""
        self._settle(False)

    def keyPressEvent(self, event) -> None:                  # noqa: N802
        # Esc = 取消，Enter = 确认
        if event.key() == Qt.Key_Escape:
            self._settle(False)
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._settle(True)
        else:
            super().keyPressEvent(event)


def show_confirm(title: str, body: str, ok_text: str, cancel_text: str,
                 timeout_s: int, timeout_ok: bool, on_result) -> None:
    """显示确认弹窗（任意线程可调）。

    on_result(bool) 在 GUI 线程回调：True=确认（含超时按确认），False=取消。
    若已有旧弹窗，旧的按「取消」结算后再弹新的。
    """
    def _run() -> None:
        global _window
        if _window is not None:
            try:
                _window.force_cancel()
            except Exception:                                # noqa: BLE001
                pass
            _window = None
        try:
            _window = _ConfirmWindow(title, body, ok_text, cancel_text,
                                     timeout_s, timeout_ok, on_result)
            _window.show()
            logger.info("[confirm_dialog] 弹窗已显示: {}", title)
        except Exception as e:                               # noqa: BLE001
            logger.warning("[confirm_dialog] 弹窗创建失败: {}", e)
            try:
                on_result(False)                # 弹不出来就按取消，别把链条挂死
            except Exception:                                # noqa: BLE001
                pass
    _on_gui(_run)


def close_confirm(result_ok: bool = False) -> None:
    """外部要求关闭当前弹窗（如插件卸载）：按 result_ok 结算。"""
    def _run() -> None:
        global _window
        if _window is None:
            return
        try:
            if result_ok:
                _window._settle(True)
            else:
                _window.force_cancel()
        except Exception:                                    # noqa: BLE001
            pass
        _window = None
    _on_gui(_run)
