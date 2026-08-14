"""逻辑字段模型：一个字体在界面中可编辑的全部状态。"""

import os
from dataclasses import dataclass, field

LANGS = ("SC", "TC", "JA", "EN")
LANG_LABELS = {"SC": "简体", "TC": "繁體", "JA": "日文", "EN": "英文"}
LANG_PREFIX = {"SC": "简", "TC": "繁", "JA": "日", "EN": "英"}

# 表格头部 4 个临时名称列 → 占位符 code（{name_sc} 等，供文本字段引用）
NAME_TEMP_CODES = {"SC": "name_sc", "TC": "name_tc", "JA": "name_jp", "EN": "name_en"}
# 字符集列 → 占位符 code（{charset_sc} 等）
CHARSET_TEMP_CODES = {"SC": "charset_sc", "TC": "charset_tc", "JA": "charset_jp", "EN": "charset_en"}

# 方正模板中出现的全部 nameID
MANAGED_NAME_IDS = [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 256, 257, 258,
]

# 默认在表格中显示的字段（其余 name 字段由「全部字段」开关展开）
EDITABLE_NAME_IDS = [1, 2, 3, 4, 5, 6, 16, 17]

NAME_ID_LABELS = {
    0: "版权", 1: "家族名", 2: "子家族名", 3: "唯一标识", 4: "全名",
    5: "版本号", 6: "字体名", 7: "商标", 8: "厂商", 9: "设计者",
    10: "描述", 11: "厂商网址", 12: "许可网址", 13: "许可", 14: "标准变体",
    16: "首选家族名", 17: "首选子家族名", 256: "WWS家族名", 257: "WWS子家族名", 258: "调色板",
}


def _empty_names() -> dict[str, dict[int, str]]:
    return {lang: {n: "" for n in MANAGED_NAME_IDS} for lang in LANGS}


@dataclass
class FontEntry:
    """一个字体的逻辑字段。集合文件（TTC/OTC）的每个子字体单独一个实例。"""

    font_path: str = ""
    font_index: int = 0          # 集合文件内子字体序号；单字体恒为 0
    us_weight_class: int = 400
    us_width_class: int = 5
    fs_selection: int = 64       # int 位掩码；bit0 = 斜体
    num_glyphs: int = 0          # 只读
    version: str = ""            # 字体版本号（head.fontRevision 兜底），保存时写入各组 nid5
    names: dict[str, dict[int, str]] = field(default_factory=_empty_names)
    save_langs: dict[str, bool] = field(default_factory=lambda: {l: False for l in LANGS})
    temp_names: dict[str, str] = field(default_factory=lambda: {l: "" for l in LANGS})
    charsets: dict[str, str] = field(default_factory=lambda: {l: "" for l in LANGS})
    rename_template: str = ""   # 重命名模板（含 {占位符}；空=不重命名）
    template_name: str = ""     # 应用的模板名（「模板」列；解析字重/字宽/斜体占位符时按此查表）
    _raw_groups: set[tuple[int, int, int]] = field(default_factory=set, repr=False)

    @property
    def is_collection(self) -> bool:
        return self.font_path.lower().endswith((".ttc", ".otc"))

    def display_name(self) -> str:
        """表格「字体文件」列：单字体显示文件名，集合显示 文件名[序号]。"""
        base = os.path.basename(self.font_path)
        if self.is_collection:
            return f"{base}[{self.font_index}]"
        return base

    def italic(self) -> bool:
        return bool(self.fs_selection & (1 << 0))

    def set_italic(self, value: bool):
        if value:
            self.fs_selection |= 1 << 0
        else:
            self.fs_selection &= ~(1 << 0)
