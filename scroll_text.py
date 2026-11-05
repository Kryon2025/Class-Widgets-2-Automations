# -*- coding: utf-8 -*-
"""全屏文字播放：滚动 / 静止停留，右键弹出「编辑文本 / 退出」菜单。

给自动化提供两个入口：
    1. 行动「全屏滚动文字」→ show_scroll_text()
    2. 设置页手动按钮「打开全屏播放文字」→ open_editor()

设计要点：
    - 纯 QWidget 实现，不依赖宿主 QML 结构，避免跟着主程序改版失效；
    - 真·全屏、无边框、置顶，纯黑不透明背景（盖住任务栏）；
    - 右键 → 弹出菜单「编辑文本 / 退出」；触摸屏长按 0.7 秒合成同一次右键；
    - 文字宽度不超过屏幕 → 静止居中停留 p2 秒；超过 → 从右往左滚动。

线程：窗口必须在 GUI 线程创建。init() 在插件 on_load（GUI 线程）调用，
建立信号桥；其它线程调 show_scroll_text() 也能安全落地到 GUI 线程。
"""
from __future__ import annotations

import ctypes
import sys

from loguru import logger

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor, QContextMenuEvent, QFont, QGuiApplication, QPainter,
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QMenu, QPlainTextEdit,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

# 速度档位（像素/秒）
SPEEDS = {"slow": 100, "normal": 220, "fast": 380}
SPEED_KEYS = ("slow", "normal", "fast")
SPEED_LABELS = {"slow": "慢", "normal": "正常", "fast": "快"}
SIZE_PX = {"small": 48, "normal": 72, "large": 120}
SIZE_KEYS = ("small", "normal", "large")
SIZE_LABELS = {"small": "小", "normal": "中", "large": "大"}

# 显示模式：全屏铺满 / 屏幕上方一条横幅
MODES = ("full", "banner")
MODE_LABELS = {"full": "全屏", "banner": "顶部横幅"}
BANNER_TOP_RATIO = 0.045     # 横幅离屏幕顶端的留空（占屏幕高度的比例）
BANNER_TOP_MIN = 24          # 留空最小值（像素）
BANNER_TOP_MAX = 90          # 留空最大值（像素）
BANNER_PAD_Y = 22            # 横幅内文字上下的内边距

# 输入控件样式：一律用实色（半透明背景 + 不透明窗口会在 hover 重绘时白闪）
FIELD_STYLE = (
    "QSpinBox, QComboBox{"
    " background:#262626; color:#ffffff; border:1px solid #4a4a4a;"
    " border-radius:6px; padding:4px 6px;}"
    "QSpinBox:hover, QComboBox:hover{border-color:#6f6f6f; background:#2e2e2e;}"
    "QSpinBox:focus, QComboBox:focus{border-color:#2f7cf6; background:#2e2e2e;}"
    "QSpinBox{min-width:96px;}"
    "QSpinBox::up-button, QSpinBox::down-button{"
    " width:18px; background:#333333; border:none;}"
    "QSpinBox::up-button{border-top-right-radius:5px;}"
    "QSpinBox::down-button{border-bottom-right-radius:5px;}"
    "QSpinBox::up-button:hover, QSpinBox::down-button:hover{background:#454545;}"
    "QSpinBox::up-button:pressed, QSpinBox::down-button:pressed{background:#2f7cf6;}"
    "QSpinBox::up-arrow, QSpinBox::down-arrow{width:7px; height:7px;}"
    "QComboBox::drop-down{width:22px; border:none; background:transparent;}"
    "QComboBox::down-arrow{width:8px; height:8px;}"
    "QComboBox QAbstractItemView{background:#262626; color:#ffffff;"
    " selection-background-color:#2f7cf6; border:1px solid #4a4a4a;}"
)

LONG_PRESS_MS = 700          # 长按判定阈值（触摸屏长按 = 右键）
TOUCH_MOVE_TOLERANCE = 60    # 手指移动超过这个像素就当作滑动，不算长按
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000


def _hide_from_taskbar(w) -> None:
    """让窗口不出现在任务栏 / Alt+Tab（Windows 扩展样式 WS_EX_TOOLWINDOW）。"""
    if sys.platform != "win32":
        return
    try:
        hwnd = int(w.winId())
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TOOLWINDOW)
    except Exception as e:                       # noqa: BLE001
        logger.debug("[scroll_text] 设置任务栏隐藏失败: {}", e)
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
    """全屏置顶遮罩窗口基类。

    用 Qt.Window 而不是 Qt.Tool：Tool 窗口在 Windows 上全屏时盖不住任务栏，
    表现就是「看着不全屏」。

    右键行为：子类实现 contextMenuEvent()（播放窗口用它弹菜单）。
    触摸屏：Qt 只会把触摸合成为左键，长按拿不到右键，所以这里手动把
    「长按 0.7 秒」合成为一次右键（QContextMenuEvent），走的是同一条右键路径。
    """

    MENU_HINT = "右键：编辑 / 退出"

    def __init__(self, touch_right_click: bool = True):
        super().__init__()
        self.touch_right_click = touch_right_click
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        # 自己收触摸事件，才能判定「长按」
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        # 不透明背景：由子类 paintEvent 涂满，避免先刷一层白底再涂黑
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(False)

        # 建出原生窗口后立即打上 TOOLWINDOW 样式：全屏/横幅都不占任务栏
        _hide_from_taskbar(self)

        self._touch_pt = None
        self._touch_timer = QTimer(self)
        self._touch_timer.setSingleShot(True)
        self._touch_timer.timeout.connect(self._on_touch_long_press)

    # ── 触摸长按 → 合成右键 ─────────────────────────────
    def _on_touch_long_press(self):
        pt = self._touch_pt
        self._touch_pt = None
        if pt is not None and self.touch_right_click:
            self._fire_right_click(pt)

    def _fire_right_click(self, pos):
        """在 pos 处合成一次右键（上下文菜单）事件。"""
        p = QPoint(int(pos.x()), int(pos.y()))
        ev = QContextMenuEvent(QContextMenuEvent.Mouse, p, self.mapToGlobal(p))
        QApplication.sendEvent(self, ev)

    def touchEvent(self, ev):
        et = ev.type()
        pts = ev.points()
        if et == QEvent.TouchBegin:
            if pts:
                self._touch_pt = pts[0].position()
                self._touch_timer.start(LONG_PRESS_MS)
            ev.accept()
            return True
        if et == QEvent.TouchUpdate:
            if self._touch_pt is not None and pts:
                d = pts[0].position() - self._touch_pt
                # 手指在滑动 → 不算长按
                if abs(d.x()) + abs(d.y()) > TOUCH_MOVE_TOLERANCE:
                    self._touch_timer.stop()
                    self._touch_pt = None
            ev.accept()
            return True
        if et in (QEvent.TouchEnd, QEvent.TouchCancel):
            self._touch_timer.stop()
            self._touch_pt = None
            ev.accept()
            return True
        return super().touchEvent(ev)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(ev)

class _ScrollWindow(_BaseOverlay):
    """播放窗口：文字超宽则滚动，否则居中停留。"""

    def __init__(self, text: str, duration: int, speed: str, size: str,
                 mode: str = "full"):
        super().__init__()
        self._text = text
        self._mode = mode if mode in MODES else "full"
        self._speed_key = speed if speed in SPEEDS else "normal"
        self._size_key = size if size in SIZE_PX else "normal"
        self._speed = SPEEDS.get(speed, SPEEDS["normal"])
        self._duration = max(0, int(duration or 0))
        self._elapsed = 0.0
        self._hint_ms = 0

        px = SIZE_PX.get(size, SIZE_PX["normal"])
        self._font_px = px
        self._label = QLabel(text, self)
        f = QFont()
        f.setPixelSize(px)
        f.setBold(True)
        self._label.setFont(f)
        self._label.setStyleSheet("color: #ffffff;")
        # 文字层不接收鼠标/触摸，右键与长按照样落到窗口本身
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._label.adjustSize()

        self._hint = QLabel("右键：编辑 / 退出（触摸屏长按）", self)
        hf = QFont()
        hf.setPixelSize(20)
        self._hint.setFont(hf)
        self._hint.setStyleSheet("color: rgba(255,255,255,150);")
        self._hint.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._hint.adjustSize()

        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)
        self._static = False
        self._menu = None

    # ── 绘制 ────────────────────────────────────────────
    def paintEvent(self, ev):
        # 纯黑、不透明：不留一丝桌面透光
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 255))

    def showEvent(self, ev):
        geo = _primary_rect()
        if geo is not None:
            if self._mode == "banner":
                # 屏幕上方一条横幅：宽满屏，高度随字号自适应，顶端留一点空
                margin = int(min(BANNER_TOP_MAX,
                                 max(BANNER_TOP_MIN, geo.height() * BANNER_TOP_RATIO)))
                bh = int(self._font_px * 1.45) + BANNER_PAD_Y * 2
                bh = max(80, min(bh, int(geo.height() * 0.4)))
                self.setGeometry(geo.x(), geo.y() + margin, geo.width(), bh)
            else:
                self.setGeometry(geo)
        super().showEvent(ev)
        self.raise_()
        w, h = self.width(), self.height()
        self._label.adjustSize()
        lw, lh = self._label.width(), self._label.height()
        self._static = lw <= w - 40
        if self._static:
            self._label.move(max(0, (w - lw) // 2), max(0, (h - lh) // 2))
        else:
            self._label.move(w, max(0, (h - lh) // 2))
        if self._mode == "banner":
            self._hint.move(w - self._hint.width() - 18, 8)
        else:
            self._hint.move(w - self._hint.width() - 24, 20)
        self._timer.start()

    # ── 右键菜单 ────────────────────────────────────────
    def contextMenuEvent(self, ev):
        ev.accept()
        if self._menu is not None and self._menu.isVisible():
            return
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#1c1c1c; color:#fff; border:1px solid #3a3a3a;"
            " padding:6px; border-radius:8px;}"
            "QMenu::item{padding:8px 26px 8px 18px; border-radius:6px;}"
            "QMenu::item:selected{background:#2f7cf6;}")
        a_edit = menu.addAction("编辑文本")
        menu.addSeparator()
        a_quit = menu.addAction("退出")
        a_edit.triggered.connect(self._menu_edit)
        a_quit.triggered.connect(self.close)
        menu.aboutToHide.connect(self._menu_hidden)
        self._menu = menu
        self._timer.stop()                  # 菜单开着的时候文字先别动
        menu.popup(ev.globalPos())          # 非阻塞：不进嵌套事件循环

    def _menu_hidden(self):
        self._menu = None
        if _alive(self) and self.isVisible():
            self._timer.start(FRAME_MS)     # 只是关掉菜单 → 继续播

    def _menu_edit(self):
        text, dur = self._text, self._duration
        speed, size = self._speed_key, self._size_key
        mode = self._mode
        self.close()
        open_editor(text, dur, speed, size, mode)

    # ── 动画 ────────────────────────────────────────────
    def _tick(self):
        self._elapsed += FRAME_MS / 1000.0
        self._hint_ms += FRAME_MS
        if self._hint_ms > 3000 and self._hint.isVisible():
            self._hint.hide()

        if self._static:
            # 静止：填 0 = 一直显示，直到右键菜单 / Esc 手动关掉
            if self._duration and self._elapsed >= self._duration:
                self.close()
            return

        self._label.move(self._label.x() - int(self._speed * FRAME_MS / 1000.0), self._label.y())
        # 滚到最后一个字完全离开屏幕：到时就关，没到时或时长 0 就从右边重新进来。
        # 注意：时长到了也不能把正在滚的半截字切掉，必须等这一段滚完，
        # 否则会出现「话没看完横幅就没了」。
        if self._label.x() + self._label.width() < 0:
            if self._duration and self._elapsed >= self._duration:
                logger.info("[scroll_text] 滚动播完且到时，关闭（{} 秒）", self._duration)
                self.close()
            else:
                self._label.move(self.width() + 40, self._label.y())


class _EditorWindow(_BaseOverlay):
    """手动触发：输入文字后直接播放。输入区放在屏幕上方，避免被屏幕键盘挡住。"""

    def __init__(self, text: str = "", duration: int = 0,
                 speed: str = "normal", size: str = "normal",
                 mode: str = "full"):
        # 编辑器里右键留给输入框自己的粘贴菜单，不合成右键
        super().__init__(touch_right_click=False)
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

        tip = QLabel("输入要显示的文字，点「开始播放」。播放时右键（触屏长按）可编辑文字或退出。", self)
        tip.setStyleSheet("color: rgba(255,255,255,170);")
        tip.setWordWrap(True)
        root.addWidget(tip)

        self.edit = QPlainTextEdit(self)
        self.edit.setPlaceholderText("在这里输入文字…")
        if text:
            self.edit.setPlainText(text)
        f = QFont()
        f.setPixelSize(24)
        self.edit.setFont(f)
        self.edit.setStyleSheet(
            "QPlainTextEdit{background:#1c1c1c; color:#ffffff;"
            " border:1px solid #4a4a4a; border-radius:8px; padding:10px;}"
            "QPlainTextEdit:focus{border-color:#2f7cf6;}")
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
        self.dur.setValue(max(0, int(duration or 0)))
        self.dur.setStyleSheet(FIELD_STYLE)
        row.addWidget(self.dur)

        row.addWidget(lab("速度"))
        self.speed = QComboBox(self)
        self.speed.addItems([SPEED_LABELS[k] for k in SPEED_KEYS])
        self.speed.setCurrentIndex(SPEED_KEYS.index(
            speed if speed in SPEEDS else "normal"))
        self.speed.setStyleSheet(FIELD_STYLE)
        row.addWidget(self.speed)

        row.addWidget(lab("字号"))
        self.size = QComboBox(self)
        self.size.addItems([SIZE_LABELS[k] for k in SIZE_KEYS])
        self.size.setCurrentIndex(SIZE_KEYS.index(
            size if size in SIZE_PX else "normal"))
        self.size.setStyleSheet(FIELD_STYLE)
        row.addWidget(self.size)

        row.addWidget(lab("显示"))
        self.mode = QComboBox(self)
        self.mode.addItems([MODE_LABELS[k] for k in MODES])
        self.mode.setCurrentIndex(MODES.index(
            mode if mode in MODES else "full"))
        self.mode.setStyleSheet(FIELD_STYLE)
        row.addWidget(self.mode)
        row.addStretch(1)

        start = QPushButton("开始播放", self)
        start.setStyleSheet(
            "QPushButton{background:#2f7cf6; color:#fff; padding:8px 18px; border-radius:6px;}")
        start.clicked.connect(self._start)
        row.addWidget(start)

        close = QPushButton("取消", self)
        close.setStyleSheet(
            "QPushButton{background:#333333; color:#ffffff; padding:8px 18px;"
            " border-radius:6px;}"
            "QPushButton:hover{background:#3f3f3f;}"
            "QPushButton:pressed{background:#2a2a2a;}")
        close.clicked.connect(self.close)
        row.addWidget(close)
        root.addLayout(row)

        root.addStretch(1)          # 其余空间留白：键盘弹起时也挡不到上面的输入区

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 255))

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
        speed = SPEED_KEYS[self.speed.currentIndex()]
        size = SIZE_KEYS[self.size.currentIndex()]
        mode = MODES[self.mode.currentIndex()]
        dur = int(self.dur.value())
        self.close()
        show_scroll_text(text, dur, speed, size, mode)


def _forget_window(*_a):
    global _window
    _window = None


def _forget_editor(*_a):
    global _editor
    _editor = None


def show_scroll_text(text: str, duration: int = 0, speed: str = "normal",
                     size: str = "normal", mode: str = "full") -> None:
    """弹出播放窗口（可从任意线程调用）。

    mode="full" 全屏铺满；mode="banner" 屏幕上方一条横幅（不挡下面内容）。
    """

    def _run():
        global _window
        text_ = str(text or "").strip()
        if not text_:
            logger.warning("[scroll_text] 文字为空，跳过")
            return
        mode_ = mode if mode in MODES else "full"
        if _alive(_window):
            _window.close()
        _window = _ScrollWindow(text_, duration, speed, size, mode_)
        _window.destroyed.connect(_forget_window)
        if mode_ == "banner":
            _window.show()              # 几何尺寸在 showEvent 里按横幅定
        else:
            _window.showFullScreen()
        _window.raise_()
        logger.info("[scroll_text] 开始播放: {} 字, 时长 {}s, 速度 {}, 字号 {}, 模式 {}",
                    len(text_), duration, speed, size, mode_)

    _on_gui(_run)


def open_editor(text: str = "", duration: int = 0, speed: str = "normal",
                size: str = "normal", mode: str = "full") -> None:
    """打开手动输入窗口（设置页按钮用；播放窗口的「编辑文本」也会调它并预填内容）。"""

    def _run():
        global _editor
        if _alive(_editor):
            _editor.raise_()
            _editor.activateWindow()
            return
        _editor = _EditorWindow(text, duration, speed, size, mode)
        _editor.destroyed.connect(_forget_editor)
        _editor.showFullScreen()
        _editor.raise_()
        _editor.activateWindow()

    _on_gui(_run)
