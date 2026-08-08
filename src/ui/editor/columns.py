"""列定义：表格列的 key / 中文表头 / 编辑类型 与 显示·解析辅助函数。"""

from dataclasses import dataclass

from PySide6.QtCore import Qt

from core.constants import FONT_WEIGHT, FONT_WIDTH
from core.models import EDITABLE_NAME_IDS, LANG_PREFIX, LANGS, MANAGED_NAME_IDS, NAME_ID_LABELS

# 单元格输入提示（模板版本号占位）用自定义数据角色返回
PLACEHOLDER_ROLE = Qt.ItemDataRole.UserRole + 1


@dataclass(frozen=True)
class ColumnDef:
    key: tuple            # ("fixed", tag) | ("save", lang) | ("lang", lang, nameID)
    header: str
    kind: str             # ro | text | weight | width | italic | save
    editable: bool = True


def _lang_header(lang: str, name_id: int) -> str:
    return f"{LANG_PREFIX[lang]}·{NAME_ID_LABELS[name_id]}"


def build_columns() -> list[ColumnDef]:
    """全部列：固定列 + 4 保存列 + 每语言组全部 20 个 name 字段。

    默认只显示 EDITABLE_NAME_IDS 之外的列由视图隐藏（set_extra_fields_visible）。
    """
    cols: list[ColumnDef] = [
        ColumnDef(("fixed", "fontPath"), "字体文件", "ro", editable=False),
        ColumnDef(("fixed", "weight"), "字重", "weight"),
        ColumnDef(("fixed", "width"), "字宽", "width"),
        ColumnDef(("fixed", "italic"), "斜体", "italic"),
        ColumnDef(("fixed", "numGlyphs"), "字形数", "ro", editable=False),
    ]
    for lang in LANGS:
        cols.append(ColumnDef(("save", lang), f"保存·{LANG_PREFIX[lang]}", "save"))
    for lang in LANGS:
        for nid in MANAGED_NAME_IDS:
            cols.append(ColumnDef(("lang", lang, nid), _lang_header(lang, nid), "text"))
    return cols


def is_default_visible(key: tuple) -> bool:
    """是否默认显示的列（非 EDITABLE_NAME_IDS 的 name 字段默认隐藏）。"""
    if key[0] == "lang":
        return key[2] in EDITABLE_NAME_IDS
    return True


# ---------------------------------------------------------------- 字重/字宽/斜体

def weight_items() -> list[tuple[int, str]]:
    return [(v, (lbl or str(v))) for v, (_, lbl, _) in FONT_WEIGHT.items()]


def width_items() -> list[tuple[int, str]]:
    items = []
    for v, (_, lbl, _) in FONT_WIDTH.items():
        items.append((v, "正常" if v == 5 else (lbl or str(v))))
    return items


ITALIC_ITEMS: list[tuple[bool, str]] = [(False, "正常"), (True, "斜体")]


def format_weight(value) -> str:
    if value in FONT_WEIGHT:
        return FONT_WEIGHT[value][1] or str(value)
    return str(value)


def format_width(value) -> str:
    if value == 5:
        return "正常"
    if value in FONT_WIDTH:
        return FONT_WIDTH[value][1] or str(value)
    return str(value)


def format_italic(value) -> str:
    return "斜体" if value else "正常"


def parse_weight(text) -> int | None:
    t = (text or "").strip()
    if not t:
        return None
    try:
        return int(t)
    except ValueError:
        pass
    for v, (en, sc, _) in FONT_WEIGHT.items():
        if t == sc or t == en:
            return v
    return None


def parse_width(text) -> int | None:
    t = (text or "").strip()
    if not t:
        return None
    if t == "正常":
        return 5
    try:
        return int(t)
    except ValueError:
        pass
    for v, (en, sc, _) in FONT_WIDTH.items():
        if t == sc or t == en or (v == 5 and t == "Normal"):
            return v
    return None


def parse_italic(text) -> bool:
    t = (text or "").strip()
    return t in ("斜体", "True", "true", "是", "1")
