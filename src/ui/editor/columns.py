"""列定义：表格列的 key / 中文表头 / 编辑类型 与 显示·解析辅助函数。"""

from dataclasses import dataclass

from PySide6.QtCore import Qt

from core.models import EDITABLE_NAME_IDS, LANG_PREFIX, LANGS, MANAGED_NAME_IDS, NAME_ID_LABELS
from core.translations import weight_label, weight_labels, width_label, width_labels

# 单元格输入提示（模板版本号占位）用自定义数据角色返回
PLACEHOLDER_ROLE = Qt.ItemDataRole.UserRole + 1

# 语言英文代号（用于列英文别名）
LANG_EN = {"SC": "SC", "TC": "TC", "JA": "JA", "EN": "EN"}

# nameID → 英文名（列英文别名）
NAME_ID_EN = {
    0: "Copyright", 1: "Family", 2: "Subfamily", 3: "Unique ID", 4: "Full Name",
    5: "Version", 6: "PostScript Name", 7: "Trademark", 8: "Manufacturer",
    9: "Designer", 10: "Description", 11: "Vendor URL", 12: "License URL",
    13: "License", 14: "Standard Variants", 16: "Preferred Family",
    17: "Preferred Subfamily", 256: "WWS Family", 257: "WWS Subfamily", 258: "Palette",
}


@dataclass(frozen=True)
class ColumnDef:
    key: tuple            # ("fixed", tag) | ("save", lang) | ("lang", lang, nameID)
    header: str
    kind: str             # ro | text | weight | width | italic | save
    editable: bool = True
    en: str = ""          # 英文别名（列头 tooltip / 重命名变量备注）


def _lang_header(lang: str, name_id: int) -> str:
    return f"{LANG_PREFIX[lang]}·{NAME_ID_LABELS[name_id]}"


def _lang_en(lang: str, name_id: int) -> str:
    return f"{LANG_EN[lang]} {NAME_ID_EN[name_id]}"


def build_columns() -> list[ColumnDef]:
    """全部列：4 临时名称列 + 固定列 + 4 保存列 + 每语言组全部 20 个 name 字段。

    默认只显示 EDITABLE_NAME_IDS 之外的列由视图隐藏（set_extra_fields_visible）。
    """
    cols: list[ColumnDef] = []
    # 表格头部 4 列：临时名称（字体名·简/繁/日/英），供 {name_sc} 等占位符引用
    for lang in LANGS:
        cols.append(ColumnDef(("temp", lang), f"字体名·{LANG_PREFIX[lang]}", "text",
                              en=f"Temp Name {LANG_EN[lang]}"))
    cols += [
        ColumnDef(("fixed", "fontPath"), "字体文件", "ro", editable=False, en="Font File"),
        ColumnDef(("fixed", "renameTemplate"), "重命名模板", "text", en="Rename Template"),
        ColumnDef(("fixed", "weight"), "字重", "weight", en="Weight"),
        ColumnDef(("fixed", "width"), "字宽", "width", en="Width"),
        ColumnDef(("fixed", "italic"), "斜体", "italic", en="Italic"),
        ColumnDef(("fixed", "numGlyphs"), "字形数", "ro", editable=False, en="Glyph Count"),
    ]
    # 字形数后面 4 列：字符集（简体/繁体/GBK 等），供 {charset_sc} 等占位符引用
    for lang in LANGS:
        cols.append(ColumnDef(("charset", lang), f"字符集·{LANG_PREFIX[lang]}", "text",
                              en=f"Charset {LANG_EN[lang]}"))
    for lang in LANGS:
        cols.append(ColumnDef(("save", lang), f"保存·{LANG_PREFIX[lang]}", "save",
                              en=f"Save {LANG_EN[lang]}"))
    for lang in LANGS:
        for nid in MANAGED_NAME_IDS:
            cols.append(ColumnDef(("lang", lang, nid), _lang_header(lang, nid), "text",
                                  en=_lang_en(lang, nid)))
    return cols


def is_default_visible(key: tuple) -> bool:
    """是否默认显示的列（非 EDITABLE_NAME_IDS 的 name 字段默认隐藏）。"""
    if key[0] == "lang":
        return key[2] in EDITABLE_NAME_IDS
    return True


# ---------------------------------------------------------------- 字重/字宽/斜体

def weight_items() -> list[tuple[int, str]]:
    # 下拉显示「数值 · 英文标签」（如 400 · Regular），数值与翻译页一一对应
    return [(v, f"{v} · {weight_label(v, 'EN')}") for v in sorted(weight_labels("SC"))]


def width_items() -> list[tuple[int, str]]:
    return [(v, width_label(v, "SC")) for v in sorted(width_labels("SC"))]


def format_weight(value) -> str:
    # 与下拉项一致的显示格式：数值 · 英文标签
    return f"{value} · {weight_label(value, 'EN')}"


def format_width(value) -> str:
    return width_label(value, "SC")


def format_italic(value) -> str:
    return "斜体" if value else "正常"


def _match_label(labels: dict[int, str], text: str) -> int | None:
    for v, lbl in labels.items():
        if text == lbl:
            return v
    return None


def parse_weight(text) -> int | None:
    t = (text or "").strip()
    if not t:
        return None
    try:
        return int(t)
    except ValueError:
        pass
    # 显示格式「400 · Regular」：取数值前缀
    head = t.split(" · ")[0].strip()
    if head.isdigit():
        return int(head)
    for lang in LANGS:
        v = _match_label(weight_labels(lang), t)
        if v is not None:
            return v
    return None


def parse_width(text) -> int | None:
    t = (text or "").strip()
    if not t:
        return None
    try:
        return int(t)
    except ValueError:
        pass
    for lang in LANGS:
        v = _match_label(width_labels(lang), t)
        if v is not None:
            return v
    return None


def parse_italic(text) -> bool:
    t = (text or "").strip()
    return t in ("斜体", "True", "true", "是", "1")
