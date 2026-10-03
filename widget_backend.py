"""桌面小组件的后端：把自动化引擎的状态喂给 qml/widget.qml。

主程序通过 WidgetLoader 把本对象赋给 widget 的 `backend` 属性
（src/qml/ClassWidgets/Components/WidgetLoader.qml:65）。
"""

from __future__ import annotations

import json

from PySide6.QtCore import QObject, Signal, Slot


class AutomationsWidgetBackend(QObject):
    """小组件后端：暴露自动化条数与当前运行中条数。"""

    changed = Signal()

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self._plugin = plugin

    def _engine(self):
        return getattr(self._plugin, "_engine", None)

    @Slot(result=str)
    def statusJson(self) -> str:
        """{"total": 总条数, "enabled": 已启用, "active": 正在生效}"""
        engine = self._engine()
        if engine is None:
            return json.dumps({"total": 0, "enabled": 0, "active": 0})

        try:
            rules = engine.get_rules() or []
        except Exception:
            rules = []

        enabled = 0
        for rule in rules:
            try:
                if rule.get("enabled", True):
                    enabled += 1
            except Exception:
                pass

        try:
            active = len(getattr(engine, "_active", {}) or {})
        except Exception:
            active = 0

        return json.dumps({"total": len(rules), "enabled": enabled, "active": active})
