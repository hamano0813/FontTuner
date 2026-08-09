"""运行时可写路径解析。

数据布局随运行模式变化，本模块总是「上三级」定位根目录：
- 开发态：src/core/paths.py → 仓库根（config.json、data/ 就在仓库根）。
- 部署态：script/core/paths.pyc → 安装根 {app}（源码已编译为 script/ 下的 .pyc）。

config.json 与 data/ 下文件（templates/translations/fontmgr_cache）都是运行时写入的。
默认写安装根；若安装根不可写（如装到 Program Files），回落 %APPDATA%\\FontTuner。
"""

import os
from pathlib import Path


def _try_write(path: Path) -> bool:
    probe = path / ".write_probe"
    try:
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def user_data_dir() -> Path:
    """当前模式下可写的数据根目录（安装根可写则用之，否则 %APPDATA%\\FontTuner）。"""
    root = Path(__file__).resolve().parent.parent.parent
    root.mkdir(parents=True, exist_ok=True)
    if _try_write(root):
        return root
    base = os.environ.get("APPDATA") or str(Path.home())
    fallback = Path(base) / "FontTuner"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


# 仓库/安装根目录（路径本身，不随写权限回落）
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = user_data_dir() / "data"
TEMPLATES_PATH = DATA_DIR / "templates.json"
TRANSLATIONS_PATH = DATA_DIR / "translations.json"
