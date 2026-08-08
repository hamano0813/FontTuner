from pathlib import Path

# 仓库根目录（src/core/paths.py 向上三级）
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"
TEMPLATES_PATH = DATA_DIR / "templates.json"
TRANSLATIONS_PATH = DATA_DIR / "translations.json"
