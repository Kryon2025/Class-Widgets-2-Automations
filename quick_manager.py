# -*- coding: utf-8 -*-
"""快捷面板：快捷管理自动化。

托盘面板（快捷面板）里的一个快捷条目，点开是一个小窗：
列出全部自动化，每行「恢复」「启用」两个勾选框，勾选即改、立即保存。
设置页如果开着，会收到 rulesChanged 自动刷新卡片状态。
"""
from __future__ import annotations

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)


class QuickRuleManager(QWidget):
    """快捷管理自动化：一屏勾完所有规则的「恢复 / 启用」。"""

    def __init__(self, plugin, parent: QWidget | None = None):
        super().__init__(parent)
        self._plugin = plugin
        self._rows: list[tuple[str, QCheckBox, QCheckBox]] = []
        self.setWindowTitle("快捷管理自动化")
        # 与「窗口调试」同一套：置顶小窗，不占任务栏
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)
        self.resize(480, 540)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        title = QLabel("快捷管理自动化")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        outer.addWidget(title)

        hint = QLabel("勾选立即生效，自动保存：左边是「恢复」，右边是「启用」。")
        hint.setWordWrap(True)
        outer.addWidget(hint)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(6)
        self._scroll.setWidget(self._body)
        outer.addWidget(self._scroll, 1)

        buttons = QHBoxLayout()
        reload_btn = QPushButton("刷新")
        reload_btn.clicked.connect(self.reload)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        buttons.addWidget(reload_btn)
        buttons.addStretch(1)
        buttons.addWidget(close_btn)
        outer.addLayout(buttons)

        self.reload()

    # ── 数据 ────────────────────────────────────────────────

    def _engine(self):
        return getattr(self._plugin, "_engine", None)

    @staticmethod
    def _name_of(rule: dict) -> str:
        name = str(rule.get("name") or "").strip() or "未命名自动化"
        if not rule.get("enabled", True):
            name += "（已停用）"
        return name

    # ── 界面 ────────────────────────────────────────────────

    def reload(self) -> None:
        """按当前规则重建列表（打开窗口、点「刷新」时调用）。"""
        while self._body_layout.count():
            item = self._body_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._rows = []
        engine = self._engine()
        rules = list(engine.get_rules()) if engine is not None else []
        if not rules:
            self._body_layout.addWidget(QLabel("还没有自动化规则，先在「设置 → 自动化」里新建一条。"))
            self._body_layout.addStretch(1)
            return
        for rule in rules:
            self._body_layout.addWidget(self._make_row(rule))
        self._body_layout.addStretch(1)
        logger.debug("[automations] 快捷管理自动化：列出 {} 条规则", len(rules))

    def _make_row(self, rule: dict) -> QWidget:
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(8)

        name = QLabel(self._name_of(rule))
        lay.addWidget(name, 1)

        uid = str(rule.get("uid") or "")
        revert_box = QCheckBox("恢复")
        revert_box.setChecked(bool(rule.get("revert")))
        enabled_box = QCheckBox("启用")
        enabled_box.setChecked(bool(rule.get("enabled")))
        # 用 uid 定位规则：列表刷新后下标会变
        revert_box.toggled.connect(
            lambda on, u=uid: self._apply(u, revert=bool(on)))
        enabled_box.toggled.connect(
            lambda on, u=uid: self._apply(u, enabled=bool(on)))
        lay.addWidget(revert_box)
        lay.addWidget(enabled_box)
        self._rows.append((uid, revert_box, enabled_box))
        return box

    # ── 改规则 ──────────────────────────────────────────────

    def _apply(self, uid: str, enabled: bool | None = None,
               revert: bool | None = None) -> None:
        engine = self._engine()
        if engine is None or not uid:
            return
        for rule in engine.get_rules():
            if str(rule.get("uid") or "") != uid:
                continue
            if enabled is not None:
                rule["enabled"] = bool(enabled)
            if revert is not None:
                rule["revert"] = bool(revert)
            engine.save()
            logger.info("[automations] 快捷面板：{}{}", uid,
                        ("" if enabled is None else (" 启用=" + str(enabled)))
                        + ("" if revert is None else (" 恢复=" + str(revert))))
            try:
                self._plugin.rulesChanged.emit()
            except Exception:                            # noqa: BLE001
                pass
            break
