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
            themes = []
            if tm is not None:
                # 不同版本里 themes 可能是 list 属性，也可能是方法
                for name in ("themes", "theme_list", "themes_list", "list"):
                    val = getattr(tm, name, None)
                    if val is None:
                        continue
                    themes = val() if callable(val) else val
                    if themes:
                        break
                if not themes:
                    for name in ("get_themes", "getThemes", "all_themes"):
                        fn = getattr(tm, name, None)
                        if callable(fn):
                            themes = fn() or []
                            if themes:
                                break

            def field(t, key, default=""):
                if isinstance(t, dict):
                    return t.get(key, default)
                return getattr(t, key, default)

            out = []
            for t in themes or []:
                tid = field(t, "id") or field(t, "name") or ""
                name = field(t, "name") or tid
                if tid:
                    out.append([str(tid), str(name)])
            return json.dumps(out, ensure_ascii=False)
        except Exception as e:
            logger.warning("[automations] 读取主题失败: {}", e)
            return "[]"

    @Slot(result=str)
    def getCachedAppsJson(self) -> str:
        """已安装应用的磁盘缓存（瞬时返回）。没有缓存时顺手启动后台预枚举。

        绝不在图形线程上同步枚举：那要起一次 PowerShell（约 3 秒），
        会卡住事件循环，并会让主程序在 QML 引擎层崩溃。
        """
        try:
            import app_index
            cached = app_index.cached_apps_json()
            if not cached:
                app_index.prefetch_async()
            return cached
        except Exception as e:
            logger.warning("[automations] 读取应用缓存失败: {}", e)
            return ""

    @Slot(result=str)
    def pickExeFile(self) -> str:
        """系统原生文件选择框：挑一个 .exe，返回完整路径（取消则返回空串）。

        只在用户点「浏览…」时调用，是主动触发的模态框，
        不参与 QML 布局，也不触碰任何界面对象，因此没有崩溃风险。
        """
        try:
            from PySide6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getOpenFileName(
                None, "选择程序", "", "可执行文件 (*.exe);;所有文件 (*.*)")
            return path or ""
        except Exception as e:  # noqa: BLE001
            logger.warning("[automations] 打开文件选择框失败: {}", e)
            return ""

    @Slot(result=str)
    def pickSoundFile(self) -> str:
        """系统原生文件选择框：挑一个铃声文件（.wav），取消返回空串。"""
        try:
            from PySide6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getOpenFileName(
                None, "选择铃声", "", "声音文件 (*.wav);;所有文件 (*.*)")
            return path or ""
        except Exception as e:  # noqa: BLE001
            logger.warning("[automations] 打开铃声选择框失败: {}", e)
            return ""

    @Slot(result=str)
    def pickFolder(self) -> str:
        """系统原生目录选择框：返回目录，取消则返回空串。"""
        try:
            from PySide6.QtWidgets import QFileDialog
            return QFileDialog.getExistingDirectory(None, "选择工作目录", "") or ""
        except Exception as e:  # noqa: BLE001
            logger.warning("[automations] 打开目录选择框失败: {}", e)
            return ""

    @Slot(result=bool)
    def prefetchAppsAsync(self) -> bool:
        """后台线程强制重枚举安装应用（不阻塞界面）。

        QML 侧轮询 getCachedAppsJson() 取结果即可，不要用会同步跑
        PowerShell 的 refreshInstalledAppsJson()。
        """
        import app_index
        app_index.prefetch_async(force=True)
        return True

    @Slot(result=str)
    def getInstalledAppsJson(self) -> str:
        """已安装应用列表（开始菜单 + App Paths + UWP/商店应用），供「打开应用」选用。"""
        try:
            import app_index
            return app_index.list_apps_json()
        except Exception as e:
            logger.warning("[automations] 枚举已安装应用失败: {}", e)
            return "[]"

    @Slot(result=str)
    def refreshInstalledAppsJson(self) -> str:
        """强制重新枚举已安装应用（设置页的「刷新列表」）。"""
        try:
            import app_index
            return app_index.list_apps_json(force=True)
        except Exception as e:
            logger.warning("[automations] 刷新已安装应用失败: {}", e)
            return "[]"

    @Slot(str, str, str, result=bool)
    def launchApp(self, target: str, args: str, cwd: str) -> bool:
        """立刻启动一次（设置页里的「试运行」）。"""
        try:
            import app_index
            return app_index.launch(target, args, cwd)
        except Exception as e:
            logger.warning("[automations] 试运行应用失败: {}", e)
            return False

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
