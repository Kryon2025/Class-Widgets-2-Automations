# -*- coding: utf-8 -*-
"""全屏文字播放：滚动 / 静止停留，右键或长按退出。

给自动化提供两个入口：
    1. 行动「全屏滚动文字」→ show_scroll_text()
    2. 设置页手动按钮「打开全屏播放文字」→ open_editor()

设计要点：
    - 纯 QWidget 实现，不依赖宿主 QML 结构，避免跟着主程序改版失效；
    - 全屏、无边框、置顶，播放期间不抢键盘焦点以外的输入；
    - 退出方式：右键单击、长按（约 0.7 秒，触摸屏等同于右键）、Esc；
    - 文字宽度不超过屏幕 → 静止居中停留 p2 秒；超过 → 从右往左滚动。

线程：窗口必须在 GUI 线程创建。init() 在插件 on_load（GUI 线程）调用，
建立信号桥；其它线程调 show_scroll_text() 也能安全落地到 GUI 线程。
"""
from __future__ import annotations

from loguru import logger

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

# 速度档位（像素/秒）
SPEEDS = {"slow": 60, "normal": 120, "fast": 220}
SPEED_LABELS = {"slow": "慢", "normal": "正常", "fast": "快"}
SIZE_PX = {"small": 48, "normal": 72, "large": 120}
SIZE_LABELS = {"small": "小", "normal": "中", "large": "大"}

LONG_PRESS_MS = 700          # 长按判定阈值
DEFAULT_STATIC_SEC = 5       # 静止播放没钱默认停留时长
FRAME_MS = 20                # 滚动帧间隔


class _Bridge(QObject):
    """跨线程把调用丢回 GUI 线程。"""

    invoke = Signal(object)


_bridge: _Bridge | None = None
_window: "_ScrollWindow | None" = None
_editor: "_EditorWindow | None" = None


def init() -> None:
    """在 GUI 线程调用一次，建立信号桥。"""
    global _bridge
    if _bridge is None:
        _bridge = _Bridge()
        _bridge.invoke.connect(lambda fn: _safe(fn))
        logger.info("[scroll_text] GUI 桥已就绪")


def _safe(fn):
    try:
        fn()
    except Exception as e:                       # noqa: BLE001
        logger.warning("[scroll_text] 执行失败: {}", e)


def _on_gui(fn) -> None:
    app = QApplication.instance()
    if app is None:
        logger.warning("[scroll_text] 没有 QApplication，无法显示")
        return
    if _bridge is None or QApplication.instance().thread() == _bridge.thread():
        try:
            fn()
        except Exception as e:                   # noqa: BLE001
            logger.warning("[scroll_text] 执行失败: {}", e)
        return
    _bridge.invoke.emit(fn)


def _alive(w) -> bool:
    """窗口关了会被 delete（WA_DeleteOnClose），此时再访问会抛 RuntimeError。"""
    try:
        return w is not None and w.isVisible()
    except RuntimeError:
        return False


def _primary_rect():
    scr = QGuiApplication.primaryScreen()
    return scr.geometry() if scr else None


class _BaseOverlay(QWidget):
    """全屏置顶遮罩窗口基类。"""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self._press_timer = QTimer(self)
        self._press_timer.setSingleShot(True)
        self._press_timer.timeout.connect(self._on_long_press)

    def _on_long_press(self):
        self.close()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.RightButton:
            self.close()
            return
        # 左键 / 触摸按压：启动长按计时，松开前到点就退出
        self._press_timer.start(LONG_PRESS_MS)
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        self._press_timer.stop()
        super().mouseReleaseEvent(ev)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(ev)


class _ScrollWindow(_BaseOverlay):
    """播放窗口：文字超宽则滚动，否则居中停留。"""

    def __init__(self, text: str, duration: int, speed: str, size: str):
        super().__init__()
        self._text = text
        self._speed = SPEEDS.get(speed, SPEEDS["normal"])
        self._duration = max(0, int(duration or 0))
        self._elapsed = 0.0
        self._hint_ms = 0
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        px = SIZE_PX.get(size, SIZE_PX["normal"])
        self._label = QLabel(text, self)
        f = QFont()
        f.setPixelSize(px)
        f.setBold(True)
        self._label.setFont(f)
        self._label.setStyleSheet("color: #ffffff;")
        self._label.adjustSize()

        self._hint = QLabel("右键 / 长按任意位置退出", self)
        hf = QFont()
        hf.setPixelSize(20)
        self._hint.setFont(hf)
        self._hint.setStyleSheet("color: rgba(255,255,255,150);")
        self._hint.adjustSize()

        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)
        self._static = False

    # ── 绘制 ────────────────────────────────────────────
    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 235))

    def showEvent(self, ev):
        geo = _primary_rect()
        if geo is not None:
            self.setGeometry(geo)
        super().showEvent(ev)
        w, h = self.width(), self.height()
        self._label.adjustSize()
        lw, lh = self._label.width(), self._label.height()
        self._static = lw <= w - 40
        if self._static:
            self._label.move(max(0, (w - lw) // 2), max(0, (h - lh) // 2))
        else:
            self._label.move(w, max(0, (h - lh) // 2))
        self._hint.move(w - self._hint.width() - 24, 20)
        self._timer.start()

    # ── 动画 ────────────────────────────────────────────
    def _tick(self):
        self._elapsed += FRAME_MS / 1000.0
        self._hint_ms += FRAME_MS
        if self._hint_ms > 3000 and self._hint.isVisible():
            self._hint.hide()

        if self._static:
            # 静止：停留指定时长（没填就 5 秒）
            limit = self._duration or DEFAULT_STATIC_SEC
            if self._elapsed >= limit:
                self.close()
            return

        self._label.move(self._label.x() - int(self._speed * FRAME_MS / 1000.0), self._label.y())
        # 限定了时长且到点 → 提前结束
        if self._duration and self._elapsed >= self._duration:
            self.close()
            return
        if self._label.x() + self._label.width() < 0:
            self.close()


class _EditorWindow(_BaseOverlay):
    """手动触发：输入文字后直接播放。输入区放在屏幕上方，避免被屏幕键盘挡住。"""

    def __init__(self):
        super().__init__()
        # 编辑器必须能接收键盘/触摸输入：去掉基类的 WindowDoesNotAcceptFocus
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 36)
        root.setSpacing(14)

        title = QLabel("全屏播放文字", self)
        tf = QFont()
        tf.setPixelSize(30)
        tf.setBold(True)
        title.setFont(tf)
        title.setStyleSheet("color: #ffffff;")
        root.addWidget(title)

        tip = QLabel("输入要显示的文字，点「开始播放」。播放时右键或长按退出。", self)
        tip.setStyleSheet("color: rgba(255,255,255,170);")
        tip.setWordWrap(True)
        root.addWidget(tip)

        self.edit = QPlainTextEdit(self)
        self.edit.setPlaceholderText("在这里输入文字…")
        f = QFont()
        f.setPixelSize(24)
        self.edit.setFont(f)
        self.edit.setStyleSheet(
            "QPlainTextEdit{background: rgba(255,255,255,24); color:#fff;"
            " border:1px solid rgba(255,255,255,60); border-radius:8px; padding:10px;}")
        root.addWidget(self.edit)

        row = QHBoxLayout()
        row.setSpacing(10)

        def lab(t):
            w = QLabel(t, self)
            w.setStyleSheet("color: rgba(255,255,255,200);")
            return w

        row.addWidget(lab("到时自动关闭（秒，0=一直显示到退出）"))
        self.dur = QSpinBox(self)
        self.dur.setRange(0, 3600)
        self.dur.setValue(0)
        self.dur.setStyleSheet("QSpinBox{background: rgba(255,255,255,24); color:#fff; padding:4px;}")
        row.addWidget(self.dur)

        row.addWidget(lab("速度"))
        self.speed = QComboBox(self)
        self.speed.addItems([SPEED_LABELS[k] for k in ("slow", "normal", "fast")])
        self.speed.setCurrentIndex(1)
        self.speed.setStyleSheet("QComboBox{background: rgba(255,255,255,24); color:#fff; padding:4px;}")
        row.addWidget(self.speed)

        row.addWidget(lab("字号"))
        self.size = QComboBox(self)
        self.size.addItems([SIZE_LABELS[k] for k in ("small", "normal", "large")])
        self.size.setCurrentIndex(1)
        self.size.setStyleSheet("QComboBox{background: rgba(255,255,255,24); color:#fff; padding:4px;}")
        row.addWidget(self.size)
        row.addStretch(1)

        start = QPushButton("开始播放", self)
        start.setStyleSheet(
            "QPushButton{background:#2f7cf6; color:#fff; padding:8px 18px; border-radius:6px;}")
        start.clicked.connect(self._start)
        row.addWidget(start)

        close = QPushButton("取消", self)
        close.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,30); color:#fff; padding:8px 18px; border-radius:6px;}")
        close.clicked.connect(self.close)
        row.addWidget(close)
        root.addLayout(row)

        root.addStretch(1)          # 其余空间留白：键盘弹起时也挡不到上面的输入区

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 225))

    def showEvent(self, ev):
        geo = _primary_rect()
        if geo is not None:
            self.setGeometry(geo)
        super().showEvent(ev)
        self.edit.setFocus()

    def _start(self):
        text = self.edit.toPlainText().strip()
        if not text:
            self.edit.setFocus()
            return
        speed = ("slow", "normal", "fast")[self.speed.currentIndex()]
        size = ("small", "normal", "large")[self.size.currentIndex()]
        dur = int(self.dur.value())
        self.close()
        show_scroll_text(text, dur, speed, size)


def _forget_window(*_a):
    global _window
    _window = None


def _forget_editor(*_a):
    global _editor
    _editor = None


def show_scroll_text(text: str, duration: int = 0, speed: str = "normal",
                     size: str = "normal") -> None:
    """在 GUI 线程弹出全屏播放窗口（可从任意线程调用）。"""

    def _run():
        global _window
        text_ = str(text or "").strip()
        if not text_:
            logger.warning("[scroll_text] 文字为空，跳过")
            return
        global _window
        if _alive(_window):
            _window.close()
        _window = _ScrollWindow(text_, duration, speed, size)
        _window.destroyed.connect(_forget_window)
        _window.showFullScreen()
        _window.raise_()
        logger.info("[scroll_text] 开始播放: {} 字, 时长 {}s, 速度 {}, 字号 {}",
                    len(text_), duration, speed, size)

    _on_gui(_run)


def open_editor() -> None:
    """打开手动输入窗口（设置页按钮用）。"""

    def _run():
        global _editor
        global _editor
        if _alive(_editor):
            _editor.raise_()
            _editor.activateWindow()
            return
        _editor = _EditorWindow()
        _editor.destroyed.connect(_forget_editor)
        _editor.showFullScreen()
        _editor.raise_()
        _editor.activateWindow()

    _on_gui(_run)
