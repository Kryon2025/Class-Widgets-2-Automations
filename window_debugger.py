# -*- coding: utf-8 -*-
"""窗口规则调试工具。

RinUI 窗口，实时显示当前前台窗口的句柄 / 类名 / 标题 / 状态 / 进程名 / 进程权限，
用于配置自动化规则里的「前台窗口…」条件。

为了复制时不误触导致数值变化，提供了「暂停获取」；标题和进程名可以一键复制，
也可以把整份信息导出成文本文件。
"""
from __future__ import annotations

import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication

PLUGIN_DIR = Path(__file__).resolve().parent

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
advapi32 = ctypes.windll.advapi32

SW_SHOWMAXIMIZED = 3
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TOKEN_QUERY = 0x0008
TokenElevation = 20
ERROR_ACCESS_DENIED = 5

# 64 位下必须显式声明句柄类型，否则 ctypes 默认按 int 截断句柄
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
advapi32.OpenProcessToken.restype = wintypes.BOOL
advapi32.OpenProcessToken.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]


class _WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("showCmd", wintypes.DWORD),
        ("ptMinPosition", wintypes.POINT),
        ("ptMaxPosition", wintypes.POINT),
        ("rcNormalPosition", wintypes.RECT),
    ]


class _TOKEN_ELEVATION(ctypes.Structure):
    _fields_ = [("TokenIsElevated", wintypes.DWORD)]


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


def _proc_path(pid: int) -> str:
    if not pid:
        return ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
    finally:
        kernel32.CloseHandle(handle)
    return ""


def _proc_elevation(pid: int) -> str:
    """判断目标进程是不是以管理员身份运行。

    窗口状态（最大化/最小化/全屏）来自窗口本身，和进程令牌无关，所以看窗口状态
    永远判断不出权限。要判断权限必须打开目标进程的令牌：
        OpenProcess → OpenProcessToken → GetTokenInformation(TokenElevation)
    普通权限下打开管理员进程会被 ACCESS_DENIED 拒绝，这时只能显示「未知」。
    """
    if not pid:
        return "未知"
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        if ctypes.get_last_error() == ERROR_ACCESS_DENIED:
            return "未知（无权限读取令牌）"
        return "未知"
    try:
        token = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(handle, TOKEN_QUERY, ctypes.byref(token)):
            return "未知（无权限读取令牌）"
        try:
            elevation = _TOKEN_ELEVATION()
            returned = wintypes.DWORD()
            if not advapi32.GetTokenInformation(
                    token, TokenElevation, ctypes.byref(elevation),
                    ctypes.sizeof(elevation), ctypes.byref(returned)):
                return "未知（读取令牌失败）"
            return "管理员" if elevation.TokenIsElevated else "标准权限"
        finally:
            kernel32.CloseHandle(token)
    finally:
        kernel32.CloseHandle(handle)


def _window_state(hwnd: int) -> str:
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


def foreground_info() -> dict:
    """读取当前前台窗口的一整份信息。"""
    hwnd = int(user32.GetForegroundWindow() or 0)
    if not hwnd:
        return {"handle": "", "cls": "", "title": "", "process": "",
                "pid": "", "state": "", "elevation": "", "path": ""}
    cls = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls, 256)
    title = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, title, 512)
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return {
        "handle": str(hwnd),
        "cls": cls.value or "",
        "title": title.value or "",
        "process": _proc_name(pid.value) or "",
        "pid": str(pid.value) if pid.value else "",
        "state": _window_state(hwnd),
        "elevation": _proc_elevation(pid.value),
        "path": _proc_path(pid.value),
    }


class WindowDebuggerBridge(QObject):
    """QML 后端：定时抓前台窗口信息，提供暂停 / 复制 / 导出。"""

    infoChanged = Signal()

    def __init__(self, plugin=None, parent=None):
        super().__init__(parent)
        self._plugin = plugin
        self._paused = False
        self._own_hwnd = 0
        self._info: dict = {}
        self._timer = QTimer(self)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self._refresh)

    # ── 生命周期 ────────────────────────────────────────────

    def setOwnWindow(self, hwnd: int) -> None:
        self._own_hwnd = int(hwnd or 0)

    def start(self) -> None:
        self._refresh()
        if not self._paused:
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    # ── 抓取 ────────────────────────────────────────────────

    def _refresh(self) -> None:
        if self._paused:
            return
        try:
            info = foreground_info()
        except Exception as e:                            # noqa: BLE001
            logger.debug("[automations] 窗口调试抓取失败: {}", e)
            return
        # 前台是本窗口时保留上一次的结果（用户正在看/复制）
        if self._own_hwnd and info.get("handle") == str(self._own_hwnd):
            return
        if info == self._info:
            return
        self._info = info
        self.infoChanged.emit()

    # ── QML 槽 ──────────────────────────────────────────────

    @Slot(result=str)
    def infoJson(self) -> str:
        return json.dumps(self._info or foreground_info(), ensure_ascii=False)

    @Slot(result=bool)
    def paused(self) -> bool:
        return self._paused

    @Slot(bool, result=bool)
    def setPaused(self, on: bool) -> bool:
        self._paused = bool(on)
        if self._paused:
            self._timer.stop()
            logger.debug("[automations] 窗口调试：已暂停获取")
        else:
            self._timer.start()
            self._refresh()
            logger.debug("[automations] 窗口调试：继续获取")
        return self._paused

    @Slot(str, result=str)
    def copyField(self, field: str) -> str:
        """复制某个字段到剪贴板：title / process / cls / handle / pid / state / elevation。"""
        names = {"title": "窗口标题", "process": "进程名", "cls": "窗口类名",
                 "handle": "窗口句柄", "pid": "进程 PID", "state": "窗口状态",
                 "elevation": "进程权限"}
        value = str((self._info or {}).get(field) or "")
        if not value:
            return "还没有抓到信息，稍等一下"
        QGuiApplication.clipboard().setText(value)
        return "已复制" + names.get(field, field) + "：" + value

    @Slot(result=str)
    def exportText(self) -> str:
        info = self._info or foreground_info()
        return ("窗口标题：" + str(info.get("title") or "") + "\n"
                + "窗口类名：" + str(info.get("cls") or "") + "\n"
                + "进程名：" + str(info.get("process") or "") + "\n"
                + "进程 PID：" + str(info.get("pid") or "") + "\n"
                + "进程路径：" + str(info.get("path") or "") + "\n"
                + "窗口状态：" + str(info.get("state") or "") + "\n"
                + "进程权限：" + str(info.get("elevation") or "") + "\n"
                + "窗口句柄：" + str(info.get("handle") or "") + "\n")

    @Slot(result=str)
    def exportToFile(self) -> str:
        """弹出保存框，把当前信息写成文本文件。"""
        try:
            from PySide6.QtWidgets import QFileDialog

            info = self._info or foreground_info()
            default_name = (str(info.get("process") or "窗口信息").rsplit(".", 1)[0]
                            + "-窗口信息.txt")
            path, _ = QFileDialog.getSaveFileName(
                None, "导出窗口信息", default_name, "文本文件 (*.txt)")
            if not path:
                return "已取消导出"
            Path(path).write_bytes(self.exportText().encode("utf-8"))
            return "已导出到：" + path
        except Exception as e:                            # noqa: BLE001
            logger.warning("[automations] 导出窗口信息失败: {}", e)
            return "导出失败：" + str(e)


class WindowDebugger:
    """RinUI 窗口封装（与快捷管理自动化同一种做法）。"""

    def __init__(self, plugin=None):
        from RinUI import RinUIWindow

        self._plugin = plugin
        self._bridge = WindowDebuggerBridge(plugin)
        self._window = RinUIWindow(shared_engine=False)
        self._window.engine.rootContext().setContextProperty(
            "WindowDebuggerBridge", self._bridge)
        self._window.load(PLUGIN_DIR / "qml" / "window_debugger.qml")
        # 置顶写在 QML 的 flags 里（动态 setFlag 会让 Qt 重建窗口，出现系统白边）
        try:
            self._bridge.setOwnWindow(int(self._window.root_window.winId()))
        except Exception:                                 # noqa: BLE001
            pass
        self._bridge.start()

    def show(self) -> None:
        window = getattr(self._window, "root_window", None)
        if window is None:
            return
        self._bridge.start()
        window.show()
        window.raise_()
        window.requestActivate()

    def raise_(self) -> None:
        window = getattr(self._window, "root_window", None)
        if window is not None:
            try:
                window.raise_()
            except Exception:                             # noqa: BLE001
                pass

    def activateWindow(self) -> None:
        window = getattr(self._window, "root_window", None)
        if window is not None:
            try:
                window.requestActivate()
            except Exception:                             # noqa: BLE001
                pass

    def close(self) -> None:
        self._bridge.stop()
        window = getattr(self._window, "root_window", None)
        if window is not None:
            try:
                window.close()
            except Exception:                             # noqa: BLE001
                pass

    def deleteLater(self) -> None:
        self._bridge.stop()
        window = getattr(self._window, "root_window", None)
        if window is not None:
            try:
                window.deleteLater()
            except Exception:                             # noqa: BLE001
                pass
