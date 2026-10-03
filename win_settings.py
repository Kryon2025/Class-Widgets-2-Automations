# -*- coding: utf-8 -*-
"""Kryon 自动化 —— 联动 Windows 设置。

所有对 Windows 系统设置的读写都收口在这个模块里，便于统一做备份 / 还原与风险控制，
引擎（automations.py）只调用它，不直接碰系统。

当前提供（第①片）：
    SETTINGS_PAGES / SETTINGS_LABELS   常用「系统设置」页（对应 ms-settings: 协议）
    open_page(page_id)                 打开指定系统设置页

后续会在这个文件里继续加：主题切换（Light Switch 同款）、读系统设置当条件、
监听系统设置变化当触发器 —— 都是往这里加函数，不改引擎既有逻辑。
"""

from __future__ import annotations

import os
import subprocess

from loguru import logger

# ── 「打开系统设置页」页表 ────────────────────────────────────
# 值 = ms-settings: 协议后面那一段。与 QML 里的 settingsPages 顺序保持一致。
# 协议清单参考：https://learn.microsoft.com/windows/uwp/launch-resume/launch-settings-app
SETTINGS_PAGES = (
    "personalization",     # 个性化
    "colors",              # 颜色
    "themes",              # 主题
    "display",             # 显示
    "sound",               # 声音
    "notifications",       # 通知
    "powersleep",          # 电源和睡眠
    "batterysaver",        # 电池
    "network",             # 网络状态
    "network-wifi",        # WLAN
    "bluetooth",           # 蓝牙
    "datetime",            # 日期和时间
    "language",            # 语言
    "appsfeatures",        # 应用
    "defaultapps",         # 默认应用
    "windowsupdate",       # Windows 更新
    "privacy",             # 隐私
    "gaming-gamebar",      # 游戏栏
    "easeofaccess",        # 辅助功能
    "about",               # 关于（系统信息）
)

SETTINGS_LABELS = (
    "个性化", "颜色", "主题", "显示", "声音", "通知", "电源和睡眠", "电池",
    "网络状态", "WLAN", "蓝牙", "日期和时间", "语言", "应用", "默认应用",
    "Windows 更新", "隐私", "游戏栏", "辅助功能", "关于",
)


def page_label(page_id: str) -> str:
    """把页 id 换成人看的名字（找不到就原样返回）。"""
    raw = str(page_id or "").strip()
    for pid, name in zip(SETTINGS_PAGES, SETTINGS_LABELS):
        if pid == raw:
            return name
    return raw


def open_page(page_id: str) -> bool:
    """打开一个 Windows 系统设置页。

    page_id 可以是页表里的值（如 "colors"），也可以是完整的 "ms-settings:colors"，
    或者干脆是一段 URL。优先用 os.startfile 交给系统协议处理器；失败退回 start 命令。
    返回是否成功发起（不代表用户一定看到了页面）。
    """
    raw = str(page_id or "").strip()
    if not raw:
        return False
    target = raw if ":" in raw else f"ms-settings:{raw}"
    try:
        os.startfile(target)                      # noqa: S606（Windows 专有）
        logger.info("[win_settings] 打开系统设置: {}", target)
        return True
    except Exception as e:                        # noqa: BLE001
        logger.warning("[win_settings] os.startfile 失败({}): {}，改用 start", target, e)
    try:
        subprocess.Popen(["cmd", "/c", "start", "", target], shell=False)
        logger.info("[win_settings] 打开系统设置(回退): {}", target)
        return True
    except Exception as e:                        # noqa: BLE001
        logger.warning("[win_settings] 打开系统设置失败({}): {}", target, e)
        return False


# ── 主题（深/浅色）—— Light Switch 同款 ───────────────────────
# 位置：HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize
#   AppsUseLightTheme    应用用浅色（1=浅 0=深）
#   SystemUsesLightTheme 系统用浅色（任务栏/开始菜单等）
_THEMES_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"

THEME_SCOPES = ("both", "apps", "system")
THEME_SCOPE_LABELS = ("全部（应用+系统）", "仅应用", "仅系统")
THEME_MODES = ("light", "dark", "toggle")
THEME_MODE_LABELS = ("浅色", "深色", "切换", )


def _read_reg(name: str):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _THEMES_KEY) as k:
            v, _ = winreg.QueryValueEx(k, name)
            return int(v)
    except Exception:                                    # noqa: BLE001
        return None


def _write_reg(name: str, value: int) -> None:
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _THEMES_KEY) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, int(value))


def _broadcast_change() -> None:
    """改完注册表要广播 WM_SETTINGCHANGE，否则不少程序不会立刻换肤。"""
    try:
        import ctypes
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "ImmersiveColorSet", 0x0002, 5000, None)
    except Exception as e:                               # noqa: BLE001
        logger.warning("[win_settings] 广播主题变更失败: {}", e)


def get_theme() -> dict:
    """读当前主题：{"apps": 1/0/None, "system": 1/0/None}（1=浅色）。"""
    return {"apps": _read_reg("AppsUseLightTheme"),
            "system": _read_reg("SystemUsesLightTheme")}


def _theme_names(scope: str):
    if scope == "apps":
        return ["AppsUseLightTheme"]
    if scope == "system":
        return ["SystemUsesLightTheme"]
    return ["AppsUseLightTheme", "SystemUsesLightTheme"]


def set_theme(mode: str, scope: str = "both"):
    """切换深/浅色。mode: light/dark/toggle；scope: both/apps/system。

    返回切换**之前**的原始值（供恢复用）；mode 非法或写失败返回 None。
    """
    m = str(mode or "").strip().lower()
    sc = str(scope or "both").strip().lower()
    if sc not in THEME_SCOPES:
        sc = "both"
    if m not in THEME_MODES:
        return None
    orig = get_theme()
    if m == "light":
        light = 1
    elif m == "dark":
        light = 0
    else:                                                # toggle
        cur = orig["apps"] if sc in ("both", "apps") else orig["system"]
        light = 0 if cur == 1 else 1
    try:
        for name in _theme_names(sc):
            _write_reg(name, light)
    except Exception as e:                               # noqa: BLE001
        logger.warning("[win_settings] 切换主题失败: {}", e)
        return None
    _broadcast_change()
    logger.info("[win_settings] 主题 -> {}（{}）", "浅色" if light else "深色", sc)
    return orig


def restore_theme(orig: dict) -> None:
    """把主题还原成 orig（set_theme 的返回值）。"""
    if not isinstance(orig, dict):
        return
    try:
        if orig.get("apps") is not None:
            _write_reg("AppsUseLightTheme", int(orig["apps"]))
        if orig.get("system") is not None:
            _write_reg("SystemUsesLightTheme", int(orig["system"]))
        _broadcast_change()
        logger.info("[win_settings] 主题已恢复: {}", orig)
    except Exception as e:                               # noqa: BLE001
        logger.warning("[win_settings] 恢复主题失败: {}", e)
