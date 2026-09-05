# -*- coding: utf-8 -*-
"""窗口规则调试工具。

置顶小窗，实时显示当前前台窗口的句柄 / 类名 / 标题 / 状态 / 进程名，
用于配置自动化规则里的「前台窗口…」条件。
"""

import ctypes
import os
from ctypes import wintypes

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_SHOWMAXIMIZED = 3
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class _WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("showCmd", wintypes.DWORD),
        ("ptMinPosition", wintypes.POINT),
        ("ptMaxPosition", wintypes.POINT),
        ("rcNormalPosition", wintypes.RECT),
    ]


def _proc_name(pid: int) -> str:
    if not pid:
        return ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
    finally:
        kernel32.CloseHandle(handle)
    return ""


class WindowDebugger(QWidget):
    """窗口规则调试窗口（置顶，点击其它窗口即显示其信息）。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("窗口规则调试")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)
        self.resize(400, 240)
        self._own_hwnd = int(self.winId())

        self._values: dict[str, QLabel] = {}
        layout = QVBoxLayout(self)

        hint = QLabel("点击你要查询的窗口，这里就会显示它的信息。")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        for key, name in (("handle", "窗口句柄"), ("class", "窗口类名"),
                          ("title", "窗口标题"), ("state", "窗口状态"),
                          ("process", "窗口进程")):
            row = QHBoxLayout()
            name_label = QLabel(name + "：")
            name_label.setFixedWidth(72)
            value_label = QLabel("—")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            row.addWidget(name_label)
            row.addWidget(value_label, 1)
            layout.addLayout(row)
            self._values[key] = value_label

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, 0, Qt.AlignRight)

        self._timer = QTimer(self)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _refresh(self) -> None:
        hwnd = user32.GetForegroundWindow()
        if not hwnd or int(hwnd) == self._own_hwnd:
            return  # 自身为前台时保留上次结果

        self._values["handle"].setText(str(hwnd))

        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        self._values["class"].setText(cls.value or "—")

        title = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title, 512)
        self._values["title"].setText(title.value or "—")

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        self._values["process"].setText(_proc_name(pid.value) or "—")

        self._values["state"].setText(self._window_state(hwnd))

    def _window_state(self, hwnd: int) -> str:
        if user32.IsIconic(hwnd):
            return "最小化"
        placement = _WINDOWPLACEMENT()
        placement.length = ctypes.sizeof(_WINDOWPLACEMENT)
        user32.GetWindowPlacement(hwnd, ctypes.byref(placement))
        if placement.showCmd == SW_SHOWMAXIMIZED:
            return "最大化"
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        if rect.left <= 2 and rect.top <= 2 and rect.right >= sw - 2 and rect.bottom >= sh - 2:
            return "全屏"
        return "正常"
