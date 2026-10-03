# -*- coding: utf-8 -*-
"""地基：插件自带依赖（vendor）机制。

把第三方包（wheel）随插件一起分发，首次运行时**就地解包**到插件自己的 vendor/
目录并挂进 sys.path —— 不需要 pip、不联网、不要管理员、用户零操作。

这样插件才有能力"为了完成功能给自己装东西"，而不是指望用户去装。

约定：
    <插件目录>/vendor/*.whl          随插件分发（打进 .cwplugin 里）
    解包后 <插件目录>/vendor/<pkg>/  ... 直接在 sys.path 上
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

from loguru import logger

PLUGIN_DIR = Path(__file__).resolve().parent
VENDOR_DIR = PLUGIN_DIR / "vendor"


def vendor_path() -> Path:
    return VENDOR_DIR


def ensure_sys_path() -> None:
    """把 vendor/ 挂进 sys.path（幂等），并让导入缓存失效。"""
    import importlib
    p = str(VENDOR_DIR)
    if VENDOR_DIR.is_dir() and p not in sys.path:
        sys.path.insert(0, p)
    try:
        importlib.invalidate_caches()          # 目录列表可能被缓存过，必须失效
    except Exception:                          # noqa: BLE001
        pass


def _ensure_init_py() -> int:
    """给解包出来的顶层包补 __init__.py。

    主程序是 PyInstaller 打包的，它的冻结导入器对"命名空间包"（目录里没有
    __init__.py）支持不佳 —— 像 winrt 这种正是命名空间包，会报 No module named。
    补一个空 __init__.py 变成常规包即可，对普通包无副作用。
    """
    made = 0
    if not VENDOR_DIR.is_dir():
        return made
    for d in VENDOR_DIR.iterdir():
        if not d.is_dir() or d.name.endswith(".dist-info") or d.name.startswith("_"):
            continue
        if d.name == "__pycache__":
            continue
        init = d / "__init__.py"
        if not init.exists():
            try:
                init.write_text("", encoding="utf-8")
                made += 1
            except Exception:                  # noqa: BLE001
                pass
    if made:
        logger.info("[deps] 补了 {} 个包的 __init__.py（冻结环境兼容）", made)
    return made


def bundled_wheels() -> list:
    """随插件分发的 wheel 列表。"""
    if not VENDOR_DIR.is_dir():
        return []
    return sorted(VENDOR_DIR.glob("*.whl"))


def _dist_info(whl_name: str) -> str:
    stem = whl_name[:-4] if whl_name.lower().endswith(".whl") else whl_name
    parts = stem.split("-")
    return f"{parts[0]}-{parts[1]}.dist-info" if len(parts) >= 2 else ""


def is_installed(whl_name: str) -> bool:
    di = _dist_info(whl_name)
    return bool(di) and (VENDOR_DIR / di).is_dir()


def install_wheel(whl: Path) -> bool:
    """把 wheel 就地解包到 vendor/（wheel 内容本身就在根，直接展开）。"""
    try:
        with zipfile.ZipFile(whl) as z:
            z.extractall(VENDOR_DIR)
        logger.info("[deps] 已解包 {}", whl.name)
        return True
    except Exception as e:                               # noqa: BLE001
        logger.warning("[deps] 解包失败 {}: {}", whl.name, e)
        return False


def ensure(progress=None) -> dict:
    """确保随插件分发的依赖全部就绪；progress(done, total, name) 可选回调。"""
    ensure_sys_path()
    wheels = bundled_wheels()
    total = len(wheels)
    done = 0
    for i, whl in enumerate(wheels):
        if progress:
            try:
                progress(i, total, whl.name)
            except Exception:                            # noqa: BLE001
                pass
        if is_installed(whl.name) or install_wheel(whl):
            done += 1
    _ensure_init_py()
    ensure_sys_path()
    if progress:
        try:
            progress(total, total, "")
        except Exception:                                # noqa: BLE001
            pass
    logger.info("[deps] 依赖就绪: {}/{}", done, total)
    return {"total": total, "done": done, "vendor": str(VENDOR_DIR)}


def status() -> dict:
    wheels = bundled_wheels()
    return {
        "vendor": str(VENDOR_DIR),
        "vendor_exists": VENDOR_DIR.is_dir(),
        "total": len(wheels),
        "installed": [w.name for w in wheels if is_installed(w.name)],
        "missing": [w.name for w in wheels if not is_installed(w.name)],
        "wheels": [w.name for w in wheels],
    }


def can_import(module: str) -> bool:
    """试导入一个模块（用于判断能力是否可用）。"""
    import importlib
    try:
        importlib.import_module(module)
        return True
    except Exception:                                    # noqa: BLE001
        return False
