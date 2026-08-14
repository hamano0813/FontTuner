"""字体系统级注册（会话级）、已装检测与扫描树。

包内拆分（按职责）：
- register.py   GDI 会话级注册/注销（AddFontResourceEx + WM_FONTCHANGE）
- installed.py  系统已装字体检测（注册表 Fonts 键 / Windows\\Fonts 目录）
- names.py      name 表 struct 直读（家族/子家族/版本/字形数）
- style.py      字体真实字重与斜体（OS/2 usWeightClass / head macStyle）
- cache.py      mtime/size 增量扫描缓存（data/fontmgr_cache.json）
- scan.py       文件夹扫描树（scan_folder_tree / font_node）
- system.py     全局已装字体各 face 枚举（字幕适配并入选项用）

对外公开 API 由本 __init__ 再导出，外部一律 `from core import font_register`，
保持「font_register.X」调用不变。
"""

from core.font_register.cache import load_cache, save_cache, set_hard_rescan
from core.font_register.installed import installed_font_set, is_font_installed
from core.font_register.register import register_font, unregister_font
from core.font_register.scan import font_node, scan_folder_tree
from core.font_register.style import font_style
from core.font_register.system import system_font_list

__all__ = [
    "register_font",
    "unregister_font",
    "installed_font_set",
    "is_font_installed",
    "font_style",
    "set_hard_rescan",
    "load_cache",
    "save_cache",
    "scan_folder_tree",
    "font_node",
    "system_font_list",
]
