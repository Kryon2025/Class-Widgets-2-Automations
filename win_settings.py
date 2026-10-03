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


# ── 读系统设置（当规则条件用）────────────────────────────────
# 每项：(键, 中文名, 类型, 可选值, 可选值中文)  类型 enum 用下拉，number 用输入框
SYS_RULE_KEYS = (
    ("theme_apps",   "应用主题（深/浅）", "enum", ("light", "dark"), ("浅色", "深色")),
    ("theme_system", "系统主题（深/浅）", "enum", ("light", "dark"), ("浅色", "深色")),
    ("ac_power",     "电源（接电/电池）", "enum", ("ac", "battery"), ("接电源", "用电池")),
    ("battery_percent", "电池电量 %", "number", None, None),
    ("network",      "网络", "enum", ("online", "offline"), ("已连接", "未连接")),
)

# 规则求值每秒都会调，网络 / 电池不能每次都真去连网 —— 结果缓存几秒
_sys_cache: dict = {}


def _cached(key: str, ttl: float, fn):
    import time
    now = time.time()
    hit = _sys_cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    val = fn()
    _sys_cache[key] = (now, val)
    return val


def _battery() -> dict:
    """用 GetSystemPowerStatus 读电源状态（无第三方依赖）。"""
    try:
        import ctypes

        class _SPS(ctypes.Structure):
            _fields_ = [("ACLineStatus", ctypes.c_byte),
                        ("BatteryFlag", ctypes.c_byte),
                        ("BatteryLifePercent", ctypes.c_byte),
                        ("SystemStatusFlag", ctypes.c_byte),
                        ("BatteryLifeTime", ctypes.c_ulong),
                        ("BatteryFullLifeTime", ctypes.c_ulong)]

        s = _SPS()
        ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s))
        ac = {1: "ac", 0: "battery"}.get(s.ACLineStatus, "unknown")
        pct = s.BatteryLifePercent if 0 <= s.BatteryLifePercent <= 100 else None
        return {"ac": ac, "percent": pct}
    except Exception:                                    # noqa: BLE001
        return {}


def _network_online() -> bool:
    """适配器是否处于已连接。用 InternetGetConnectedState（快，不做网络往返）。"""
    try:
        import ctypes
        return bool(ctypes.windll.wininet.InternetGetConnectedState(None, 0))
    except Exception:                                    # noqa: BLE001
        return False


def read_setting(key: str):
    """读一个系统设置项的值（读不到返回 None）。"""
    k = str(key or "").strip()
    if k == "theme_apps":
        v = _read_reg("AppsUseLightTheme")
        return None if v is None else ("light" if v == 1 else "dark")
    if k == "theme_system":
        v = _read_reg("SystemUsesLightTheme")
        return None if v is None else ("light" if v == 1 else "dark")
    if k == "ac_power":
        return _cached("ac", 3.0, lambda: _battery().get("ac"))
    if k == "battery_percent":
        return _cached("pct", 5.0, lambda: _battery().get("percent"))
    if k == "network":
        return "online" if _cached("net", 3.0, _network_online) else "offline"
    return None


def rule_match(key: str, op: str, value: str) -> bool:
    """规则条件：当前 read_setting(key) 是否满足 op value。"""
    cur = read_setting(key)
    if cur is None:
        return False
    o = str(op or "").strip() or "=="
    if o in ("!=", "<>", "≠", "不是"):
        o = "!="
    elif o in ("==", "=", "是", ""):
        o = "=="
    v = str(value or "").strip()
    if o in (">", ">=", "<", "<="):
        try:
            return {">": float(cur) > float(v), ">=": float(cur) >= float(v),
                    "<": float(cur) < float(v), "<=": float(cur) <= float(v)}[o]
        except Exception:                                # noqa: BLE001
            return False
    return str(cur) != v if o == "!=" else str(cur) == v


# ── 电源动作（零依赖，全部走系统自带命令 / API）──────────────
POWER_MODES = ("poweroff", "restart", "logoff", "sleep", "hibernate")
POWER_LABELS = ("关机", "重启", "注销", "睡眠", "休眠")


def hibernate_available() -> bool:
    """系统是否开启了休眠（关掉时 shutdown /h 会失败，界面里要置灰）。"""
    import ctypes
    try:
        return bool(ctypes.windll.powrprof.IsPwrHibernateAllowed())
    except Exception:                                    # noqa: BLE001
        return False


def power_action(mode: str) -> bool:
    """关机 / 重启 / 注销 / 睡眠 / 休眠。

    poweroff/restart/logoff 用 shutdown 命令；sleep 用 SetSuspendState；
    hibernate 用 shutdown /h（需系统已开启休眠）。全部不需要管理员。
    """
    m = str(mode or "").strip().lower()
    try:
        if m == "poweroff":
            subprocess.Popen(["shutdown", "/s", "/t", "0"])
        elif m == "restart":
            subprocess.Popen(["shutdown", "/r", "/t", "0"])
        elif m == "logoff":
            subprocess.Popen(["shutdown", "/l"])
        elif m == "sleep":
            import ctypes
            # (bHibernate=0, bForce=1, bWakeupEventsDisabled=0)
            ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
        elif m == "hibernate":
            if not hibernate_available():
                logger.warning("[win_settings] 系统未开启休眠，忽略")
                return False
            subprocess.Popen(["shutdown", "/h"])
        else:
            return False
    except Exception as e:                               # noqa: BLE001
        logger.warning("[win_settings] 电源动作失败({}): {}", m, e)
        return False
    logger.info("[win_settings] 电源动作: {}", m)
    return True


# ── 音量动作 ─────────────────────────────────────────────────
# 增大/减小/静音：发系统媒体键（零依赖，按系统档位跳）
# 设为某值：Core Audio API（走 comtypes；没装就明确报错，不静默）
VOLUME_MODES = ("up", "down", "mute", "set")
VOLUME_LABELS = ("增大", "减小", "静音（切换）", "设为指定值 %")

_VK_VOLUME_UP = 0xAF
_VK_VOLUME_DOWN = 0xAE
_VK_VOLUME_MUTE = 0xAD
_KEYEVENTF_KEYUP = 0x0002


def _tap_vk(vk: int, times: int = 1) -> None:
    import ctypes
    for _ in range(max(1, int(times))):
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, _KEYEVENTF_KEYUP, 0)


def volume_action(mode: str, value: str = "") -> bool:
    """音量：up/down/mute 用媒体键；set 用 Core Audio API 设成 value%（0-100）。"""
    m = str(mode or "").strip().lower()
    try:
        if m == "up":
            _tap_vk(_VK_VOLUME_UP, 2)
        elif m == "down":
            _tap_vk(_VK_VOLUME_DOWN, 2)
        elif m == "mute":
            _tap_vk(_VK_VOLUME_MUTE)
        elif m == "set":
            percent = max(0, min(100, int(float(str(value or "50").strip() or 50))))
            _set_volume_percent(percent)
        else:
            return False
    except Exception as e:                               # noqa: BLE001
        logger.warning("[win_settings] 音量动作失败({}): {}", m, e)
        return False
    logger.info("[win_settings] 音量动作: {} {}", m, value)
    return True


def _set_volume_percent(percent: int) -> None:
    """用 Core Audio API 把主音量设成 percent% —— 纯 ctypes 直调 COM，零第三方依赖。"""
    import ctypes
    from ctypes import POINTER, byref, c_void_p, c_wchar_p

    ole32 = ctypes.windll.ole32
    ole32.CoInitialize(None)

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                    ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]

    def guid(s: str) -> "GUID":
        g = GUID()
        ole32.CLSIDFromString(c_wchar_p(s), byref(g))
        return g

    def vt(ptr, index, restype, argtypes, *args):
        vtbl = ctypes.cast(ptr, POINTER(POINTER(c_void_p))).contents
        proto = ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)
        return proto(vtbl[index])(ptr, *args)

    enumerator = c_void_p()
    hr = ole32.CoCreateInstance(
        byref(guid("{BCDE0395-E52F-467C-8E3D-C4579291692E}")), None, 1,
        byref(guid("{A95664D2-9614-4F35-A746-DE8DB63617E6}")), byref(enumerator))
    if hr != 0 or not enumerator:
        raise OSError(f"CoCreateInstance 失败 hr={hr}")

    device = c_void_p()
    vt(enumerator, 4, ctypes.c_long, [ctypes.c_int, ctypes.c_int, POINTER(c_void_p)],
       0, 0, byref(device))                       # GetDefaultAudioEndpoint(eRender, eConsole)

    volume = c_void_p()
    vt(device, 3, ctypes.c_long,
       [POINTER(GUID), ctypes.c_ulong, c_void_p, POINTER(c_void_p)],
       byref(guid("{5CDF2C82-841E-4546-9722-0CF74078229A}")), 0x17, None, byref(volume))

    vt(volume, 7, ctypes.c_long, [ctypes.c_float, c_void_p],
       float(percent) / 100.0, None)              # SetMasterVolumeLevelScalar


def volume_percent():
    """读当前主音量（0-100）；读不到返回 None。"""
    import ctypes
    from ctypes import POINTER, byref, c_void_p, c_float, c_wchar_p

    ole32 = ctypes.windll.ole32
    ole32.CoInitialize(None)

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                    ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]

    def guid(s):
        g = GUID()
        ole32.CLSIDFromString(c_wchar_p(s), byref(g))
        return g

    def vt(ptr, index, restype, argtypes, *args):
        vtbl = ctypes.cast(ptr, POINTER(POINTER(c_void_p))).contents
        proto = ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)
        return proto(vtbl[index])(ptr, *args)

    try:
        enumerator = c_void_p()
        ole32.CoCreateInstance(
            byref(guid("{BCDE0395-E52F-467C-8E3D-C4579291692E}")), None, 1,
            byref(guid("{A95664D2-9614-4F35-A746-DE8DB63617E6}")), byref(enumerator))
        device = c_void_p()
        vt(enumerator, 4, ctypes.c_long, [ctypes.c_int, ctypes.c_int, POINTER(c_void_p)],
           0, 0, byref(device))
        volume = c_void_p()
        vt(device, 3, ctypes.c_long,
           [POINTER(GUID), ctypes.c_ulong, c_void_p, POINTER(c_void_p)],
           byref(guid("{5CDF2C82-841E-4546-9722-0CF74078229A}")), 0x17, None, byref(volume))
        f = c_float(0.0)
        vt(volume, 9, ctypes.c_long, [POINTER(c_float)], byref(f))   # GetMasterVolumeLevelScalar
        return round(f.value * 100)
    except Exception:                                    # noqa: BLE001
        return None


# ── 开机（系统本次启动后的时长）─────────────────────────────
def uptime_seconds() -> float:
    """本机本次开机至今的秒数（GetTickCount64，含睡眠时间）。"""
    import ctypes
    try:
        return ctypes.windll.kernel32.GetTickCount64() / 1000.0
    except Exception:                                    # noqa: BLE001
        return -1.0


def boot_id() -> int:
    """本次开机的标识：用「当前时间 - 开机时长」取整到分钟。"""
    import time
    up = uptime_seconds()
    if up < 0:
        return 0
    return int((time.time() - up) // 60)
