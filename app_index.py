# -*- coding: utf-8 -*-
"""已安装应用索引 + 启动。

「已安装应用列表」由三部分组成：
1. 开始菜单快捷方式（.lnk）—— 名字就是开始菜单里的中文显示名，启动交给系统；
2. 注册表 App Paths —— 没进开始菜单但注册了可执行路径的程序（chrome.exe 这类）；
3. PowerShell `Get-StartApps` —— 覆盖 UWP/商店应用，启动用 `shell:AppsFolder\\<AppID>`。

启动统一走 `launch()`；这个模块不依赖 PySide6。
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from pathlib import Path

from loguru import logger

# 结果缓存秒数：枚举 UWP 要起一次 PowerShell，不该每敲一个字跑一次
CACHE_SECONDS = 300
_CACHE: dict = {"at": 0.0, "apps": []}

CREATE_NO_WINDOW = 0x08000000

START_MENU_DIRS = (
    Path(os.environ.get("ProgramData", r"C:\ProgramData"))
    / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    Path(os.environ.get("APPDATA", ""))
    / "Microsoft" / "Windows" / "Start Menu" / "Programs",
)

APP_PATHS_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"

SHELL_PREFIX = "shell:AppsFolder\\"


def _no_window_flags() -> int:
    return CREATE_NO_WINDOW if os.name == "nt" else 0


def _from_start_menu() -> list:
    """开始菜单里的 .lnk（含中文显示名）。"""
    apps = []
    for root in START_MENU_DIRS:
        try:
            if not root.is_dir():
                continue
            for path in root.rglob("*.lnk"):
                apps.append({
                    "name": path.stem,
                    "target": str(path),
                    "kind": "lnk",
                    "source": "开始菜单",
                })
        except Exception as e:  # noqa: BLE001
            logger.debug("[automations] 读取开始菜单失败({}): {}", root, e)
    return apps


def _from_start_apps() -> list:
    """Get-StartApps：包含 UWP，AppID 可直接喂给 shell:AppsFolder。"""
    if os.name != "nt":
        return []
    command = (
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
        "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"
    )
    try:
        done = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, timeout=30, creationflags=_no_window_flags(),
        )
    except Exception as e:  # noqa: BLE001
        logger.debug("[automations] Get-StartApps 执行失败: {}", e)
        return []
    text = (done.stdout or b"").decode("utf-8", errors="replace").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except ValueError:
        logger.debug("[automations] Get-StartApps 输出不是 JSON: {}", text[:120])
        return []
    if isinstance(data, dict):
        data = [data]
    apps = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("Name") or "").strip()
        app_id = str(item.get("AppID") or "").strip()
        if not name or not app_id:
            continue
        apps.append({
            "name": name,
            "target": SHELL_PREFIX + app_id,
            "kind": "uwp" if "!" in app_id else "shell",
            "source": "开始菜单应用",
        })
    return apps


def _from_app_paths() -> list:
    """注册表 App Paths：每个子键名就是一个可执行文件名。"""
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []
    apps = []
    hives = (
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_READ | winreg.KEY_WOW64_64KEY),
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_READ | winreg.KEY_WOW64_32KEY),
        (winreg.HKEY_CURRENT_USER, winreg.KEY_READ),
    )
    for hive, access in hives:
        try:
            with winreg.OpenKey(hive, APP_PATHS_KEY, 0, access) as key:
                for index in range(winreg.QueryInfoKey(key)[0]):
                    name = winreg.EnumKey(key, index)
                    try:
                        with winreg.OpenKey(key, name) as sub:
                            target = str(winreg.QueryValue(sub, None) or "").strip('"')
                    except OSError:
                        continue
                    if not target:
                        continue
                    apps.append({
                        "name": Path(name).stem,
                        "target": target,
                        "kind": "exe",
                        "source": "App Paths",
                    })
        except OSError:
            continue
    return apps


def list_apps(force: bool = False) -> list:
    """已安装应用列表（带缓存），按名字排序、去重。"""
    now = time.time()
    if not force and _CACHE["apps"] and now - _CACHE["at"] < CACHE_SECONDS:
        return _CACHE["apps"]

    merged: dict = {}
    for app in _from_start_menu() + _from_app_paths() + _from_start_apps():
        key = str(app.get("name") or "").strip().casefold()
        if not key:
            continue
        # 同名时保留先出现的：开始菜单快捷方式 > App Paths > Get-StartApps
        merged.setdefault(key, app)

    apps = sorted(merged.values(), key=lambda a: str(a.get("name") or "").casefold())
    _CACHE["at"] = now
    _CACHE["apps"] = apps
    logger.info("[automations] 已安装应用枚举完成：{} 个", len(apps))
    return apps


def list_apps_json(force: bool = False) -> str:
    """给 QML 用的 JSON 字符串。"""
    try:
        return json.dumps(list_apps(force), ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        logger.warning("[automations] 枚举已安装应用失败: {}", e)
        return "[]"


def launch(target: str, args: str = "", cwd: str = "") -> bool:
    """启动应用 / 打开文件。

    - .exe：按参数启动（参数按 shell 规则切分）
    - .lnk / shell:AppsFolder\\… / 网址 / 文档：交给系统默认方式处理
    """
    target = str(target or "").strip()
    if not target:
        return False
    args = str(args or "").strip()
    cwd = str(cwd or "").strip()
    try:
        if target.lower().endswith(".exe"):
            argv = [target]
            if args:
                argv += shlex.split(args, posix=False)
            subprocess.Popen(argv, cwd=cwd or None, close_fds=True,
                             creationflags=_no_window_flags())
        else:
            os.startfile(target)  # type: ignore[attr-defined]
        logger.info("[automations] 打开应用: {}{}", target, f" {args}" if args else "")
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("[automations] 打开应用失败({}): {}", target, e)
        return False
