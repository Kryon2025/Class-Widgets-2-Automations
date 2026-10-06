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


def _fixup_ext_suffixes() -> int:
    """把带 ABI 标记的扩展模块(*.cp3XX-win_amd64.pyd)补一份裸 *.pyd。

    冻结版主程序的导入器对 ABI 标记后缀不一定认（如 pysqlite3 里的
    _sqlite3.cp312-win_amd64.pyd），补一份裸 .pyd 最保险（winrt/winsdk 用的就是裸名）。
    """
    made = 0
    if not VENDOR_DIR.is_dir():
        return made
    import shutil
    for pyd in VENDOR_DIR.rglob("*.pyd"):
        stem = pyd.stem                              # 例：_sqlite3.cp312-win_amd64
        if "." not in stem:
            continue
        target = pyd.with_name(stem.split(".", 1)[0] + ".pyd")   # 例：_sqlite3.pyd
        if target.exists():
            continue
        try:
            shutil.copy2(pyd, target)
            made += 1
        except Exception:                            # noqa: BLE001
            pass
    if made:
        logger.info("[deps] 补了 {} 个裸名扩展模块（冻结环境兼容）", made)
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


def _wheel_missing(whl_name: str) -> list:
    """wheel 里有、但 vendor/ 里缺（或大小不符）的文件清单。

    解包中途失败（文件被占用、杀软拦截、进程被杀）会留下一堆半成品，
    而 .dist-info 往往已经落盘 —— 只看 dist-info 会把半成品当成已完成，
    于是永远不再重解。这里逐文件核对，才能发现残缺。
    """
    whl = VENDOR_DIR / whl_name
    missing = []
    try:
        with zipfile.ZipFile(whl) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                target = VENDOR_DIR / info.filename
                try:
                    if not target.is_file() or target.stat().st_size != info.file_size:
                        missing.append(info.filename)
                except OSError:
                    missing.append(info.filename)
    except Exception as e:                               # noqa: BLE001
        # wheel 自身读不了：不能据此判定"残缺"，否则会每次启动都无限重解
        logger.debug("[deps] 无法读取 {} 核对内容: {}", whl_name, e)
        return []
    return missing


def is_installed(whl_name: str) -> bool:
    di = _dist_info(whl_name)
    if not (di and (VENDOR_DIR / di).is_dir()):
        return False
    missing = _wheel_missing(whl_name)
    if missing:
        logger.warning("[deps] {} 解包不完整，缺 {} 个文件（例：{}），将重新解包",
                       whl_name, len(missing), missing[0])
        return False
    return True


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
    _fixup_ext_suffixes()
    ensure_sys_path()
    if progress:
        try:
            progress(total, total, "")
        except Exception:                                # noqa: BLE001
            pass
    if done < total:
        logger.warning("[deps] 依赖未全部就绪: {}/{} —— 下次启动会重试解包", done, total)
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
