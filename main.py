"""Kryon 自动化 —— 为 Class Widgets 2 提供自动化能力。

实现「自动化」（触发器 + 规则集 + 行动 + 恢复）引擎，
注册为官方 AutomationTask 进入主程序调度。
"""

from __future__ import annotations

import json
from pathlib import Path

from ClassWidgets.SDK import CW2Plugin, PluginAPI
from loguru import logger
from PySide6.QtCore import Slot

from automations import RuleEngine

CFG_NAME = "com.kryon.automations.json"

# 官方自动化任务框架（主程序运行时可用；降级则用引擎自带的每秒定时器）
try:
    from src.core.automations.base import AutomationTask
    HAS_OFFICIAL_TASK = True
except Exception:
    AutomationTask = object
    HAS_OFFICIAL_TASK = False


class RuleEngineTask(AutomationTask):
    """把 RuleEngine 包装为官方 AutomationTask，纳入主程序每秒调度。"""

    def __init__(self, central, engine: RuleEngine):
        super().__init__(central)
        self._engine = engine

    @property
    def name(self) -> str:
        return "com.kryon.automations.engine"

    def update(self) -> None:
        self._engine.update()


def _app_root() -> Path:
    # <主程序根>/plugins/com.kryon.automations/main.py -> 主程序根
    return Path(__file__).resolve().parent.parent.parent


class Plugin(CW2Plugin):
    """Kryon 自动化：引擎 + 设置页后端。"""

    def __init__(self, api: PluginAPI):
        super().__init__(api)
        self._engine: RuleEngine | None = None
        self._task: RuleEngineTask | None = None
        self._debugger = None

    def on_load(self):
        super().on_load()
        storage = _app_root() / "configs" / "plugins" / CFG_NAME
        try:
            self._engine = RuleEngine(self.api, storage)
            self._engine.load()
            if HAS_OFFICIAL_TASK:
                try:
                    self._engine._tick_timer.stop()  # 由官方调度驱动
                except Exception:
                    pass
                self._task = RuleEngineTask(self.api._app, self._engine)
                self.api.automation.register(self._task)
                logger.info("[automations] 已注册官方自动化任务")
            logger.info("[automations] 引擎已启动, 规则数: {}", len(self._engine.get_rules()))
        except Exception as e:
            logger.warning("[automations] 引擎启动失败: {}", e)
            self._engine = None

        try:
            self.api.ui.register_settings_page(
                qml_path=str(Path(__file__).parent / "qml" / "settings.qml"),
                title="自动化",
                icon="ic_fluent_arrow_autofit_height_20_regular",
            )
            logger.info("[automations] 设置页注册成功")
        except Exception as e:
            logger.warning("[automations] 注册设置页失败: {}", e)

        if self._engine is not None:
            try:
                self._engine.app_started()
            except Exception as e:
                logger.warning("[automations] 启动触发失败: {}", e)

    def on_unload(self):
        super().on_unload()
        if self._task is not None:
            try:
                self.api._app.automation_manager.remove_task(self._task.name)
            except Exception:
                pass
            self._task = None
        if self._engine is not None:
            try:
                self._engine.shutdown()
            except Exception as e:
                logger.warning("[automations] 引擎停止异常: {}", e)
            self._engine = None
        if self._debugger is not None:
            try:
                self._debugger.close()
                self._debugger.deleteLater()
            except Exception:
                pass
            self._debugger = None
        logger.info("[automations] 插件已卸载")

    # ── 设置页槽 ─────────────────────────────────────────────

    @Slot(result=str)
    def getRulesJson(self) -> str:
        rules = self._engine.get_rules() if self._engine else []
        return json.dumps(rules, ensure_ascii=False)

    @Slot(str, result=bool)
    def saveRulesJson(self, rules_json: str) -> bool:
        if self._engine is None:
            return False
        try:
            data = json.loads(rules_json or "[]")
        except Exception:
            return False
        return self._engine.set_rules(data)

    @Slot(int, result=bool)
    def fireRuleNow(self, index: int) -> bool:
        if self._engine is None:
            return False
        return self._engine.fire_now(index)

    @Slot(result=bool)
    def reloadRules(self) -> bool:
        if self._engine is None:
            return False
        self._engine.load()
        return True

    @Slot(result=str)
    def getFlagsJson(self) -> str:
        """当前已设标志（供设标志/读标志参考）。"""
        flags = self._engine.get_flags() if self._engine else {}
        return json.dumps(flags, ensure_ascii=False)

    @Slot(result=str)
    def getPresetsJson(self) -> str:
        """组件方案列表（供"切换组件方案"使用）。"""
        try:
            presets = self.api.globalconfig.configs.preferences.widgets_presets or {}
            return json.dumps(sorted(str(k) for k in presets), ensure_ascii=False)
        except Exception:
            return "[]"

    @Slot(result=str)
    def getSubjectsJson(self) -> str:
        """科目名与教师名列表（供"科目是/教师是"下拉）。"""
        try:
            schedule = self.api.schedule.get()
            subjects: list[str] = []
            teachers: list[str] = []
            seen: set[str] = set()
            for s in (getattr(schedule, "subjects", None) or []):
                name = getattr(s, "name", None) or (s.get("name") if isinstance(s, dict) else None)
                simplified = getattr(s, "simplifiedName", None) or (s.get("simplifiedName") if isinstance(s, dict) else None)
                teacher = getattr(s, "teacher", None) or (s.get("teacher") if isinstance(s, dict) else None)
                label = str(name or simplified or "").strip()
                if label and label not in seen:
                    seen.add(label)
                    subjects.append(label)
                t = str(teacher or "").strip()
                if t and t not in teachers:
                    teachers.append(t)
            return json.dumps({"subjects": subjects, "teachers": teachers}, ensure_ascii=False)
        except Exception as e:
            logger.warning("[automations] 读取科目失败: {}", e)
            return json.dumps({"subjects": [], "teachers": []})

    @Slot(result=str)
    def getThemesJson(self) -> str:
        """主题列表 [[id, name], ...]（供"设置主题"下拉）。"""
        try:
            tm = getattr(self.api._app, "themeManager", None) or getattr(self.api._app, "theme_manager", None)
            themes = tm.themes() if tm else []
            out = [[str(t.get("id") or ""), str(t.get("name") or t.get("id") or "")]
                   for t in themes]
            return json.dumps(out, ensure_ascii=False)
        except Exception as e:
            logger.warning("[automations] 读取主题失败: {}", e)
            return "[]"

    @Slot()
    def openWindowDebugger(self) -> None:
        """打开窗口规则调试工具（置顶小窗，显示前台窗口信息）。"""
        try:
            if self._debugger is None:
                from window_debugger import WindowDebugger
                self._debugger = WindowDebugger()
            self._debugger.show()
            self._debugger.raise_()
            self._debugger.activateWindow()
        except Exception as e:
            logger.warning("[automations] 打开窗口调试工具失败: {}", e)
