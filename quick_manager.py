# -*- coding: utf-8 -*-
"""快捷面板：快捷管理自动化。

托盘快捷面板里的一个条目，点开是一个 RinUI 窗口（与主程序其它窗口同一套 UI）：
列出全部自动化，每行「恢复」「启用」两个勾选框，勾选即改、立即保存。
设置页如果开着，会收到 rulesChanged 自动刷新卡片状态。
"""
from __future__ import annotations

import json
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, Slot

PLUGIN_DIR = Path(__file__).resolve().parent


class QuickRuleBridge(QObject):
    """QML 窗口用的后端：只暴露读规则与改规则两个槽。"""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self._plugin = plugin

    def _engine(self):
        return getattr(self._plugin, "_engine", None)

    @Slot(result=str)
    def rulesJson(self) -> str:
        """[{uid, name, enabled, revert}, ...]，供 QML 列表显示。"""
        engine = self._engine()
        rules = list(engine.get_rules()) if engine is not None else []
        out = []
        for rule in rules:
            out.append({
                "uid": str(rule.get("uid") or ""),
                "name": str(rule.get("name") or ""),
                "enabled": bool(rule.get("enabled", True)),
                "revert": bool(rule.get("revert")),
            })
        return json.dumps(out, ensure_ascii=False)

    @Slot(str, bool, bool, result=bool)
    def setRule(self, uid: str, enabled: bool, revert: bool) -> bool:
        """按 uid 改一条规则的「启用 / 恢复」，立即保存并通知设置页。"""
        engine = self._engine()
        if engine is None or not uid:
            return False
        for rule in engine.get_rules():
            if str(rule.get("uid") or "") != uid:
                continue
            rule["enabled"] = bool(enabled)
            rule["revert"] = bool(revert)
            try:
                engine.save()
            except Exception as e:                       # noqa: BLE001
                logger.warning("[automations] 快捷面板保存失败: {}", e)
            try:
                self._plugin.rulesChanged.emit()
            except Exception:                            # noqa: BLE001
                pass
            logger.info("[automations] 快捷面板：{} 启用={} 恢复={}",
                        uid, bool(enabled), bool(revert))
            return True
        return False


class QuickRuleWindow:
    """用 RinUI 窗口承载 QML（与主程序其它窗口同一套 UI）。"""

    def __init__(self, plugin):
        from RinUI import RinUIWindow

        self._plugin = plugin
        self._bridge = QuickRuleBridge(plugin)
        self._window = RinUIWindow(shared_engine=False)
        self._window.engine.rootContext().setContextProperty(
            "QuickRuleBridge", self._bridge)
        self._window.load(PLUGIN_DIR / "qml" / "quick_manager.qml")

    def show(self) -> None:
        window = getattr(self._window, "root_window", None)
        if window is None:
            return
        window.show()
        window.raise_()
        window.requestActivate()

    def close(self) -> None:
        window = getattr(self._window, "root_window", None)
        if window is not None:
            try:
                window.close()
            except Exception:                            # noqa: BLE001
                pass

    @property
    def visible(self) -> bool:
        window = getattr(self._window, "root_window", None)
        return bool(window is not None and window.isVisible())
