"""列定义：表格列的 key / 中文表头 / 编辑类型 与 显示·解析辅助函数。"""

from dataclasses import dataclass

from PySide6.QtCore import Qt

from core.constants import WIDTH_LABELS
from core.models import EDITABLE_NAME_IDS, MANAGED_NAME_IDS, NAME_ID_LABELS

# 单元格输入提示（模板版本号占位）用自定义数据角色返回
PLACEHOLDER_ROLE = Qt.ItemDataRole.UserRole + 1

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
    key: tuple            # 父列 ("fixed", tag) | 子列 ("save",)/("temp",)/("charset",)/("lang", nameID)
    header: str
    kind: str             # ro | text | weight | width | italic | save
    editable: bool = True
    en: str = ""          # 英文别名（列头 tooltip / 重命名变量备注）


def build_columns() -> list[ColumnDef]:
    """树形列：父列（字体级，父节点行）+ 子列（语言级，4 个语言子节点行共用）。

    语言是行不是列，故子列 key 不含语言；每个子节点行填全套子列数据。
    默认只显示 EDITABLE_NAME_IDS 的 name 字段，其余由视图「全部字段」开关展开。
    """
    cols: list[ColumnDef] = []
    # ---- 父列（字体级）----
    # 模板列只读：只能通过「应用模板」覆盖，不允许手工输入
    cols.append(ColumnDef(("fixed", "templateName"), "模板", "text", editable=False, en="Template"))
    cols.append(ColumnDef(("fixed", "fontPath"), "字体文件", "ro", editable=False, en="Font File"))
    cols.append(ColumnDef(("fixed", "renameTemplate"), "重命名模板", "text", en="Rename Template"))
    cols.append(ColumnDef(("fixed", "weight"), "字重", "weight", en="Weight"))
    cols.append(ColumnDef(("fixed", "width"), "字宽", "width", en="Width"))
    cols.append(ColumnDef(("fixed", "italic"), "斜体", "italic", en="Italic"))
    cols.append(ColumnDef(("fixed", "numGlyphs"), "字形数", "ro", editable=False, en="Glyph Count"))
    # ---- 子列（语言级）----
    cols.append(ColumnDef(("save",), "保存", "save", en="Save"))
    cols.append(ColumnDef(("temp",), "字体名", "text", en="Temp Name"))
    cols.append(ColumnDef(("charset",), "字符集", "text", en="Charset"))
    for nid in MANAGED_NAME_IDS:
        cols.append(ColumnDef(("lang", nid), NAME_ID_LABELS[nid], "text", en=NAME_ID_EN[nid]))
    return cols


def is_default_visible(key: tuple) -> bool:
    """是否默认显示的列（非 EDITABLE_NAME_IDS 的 name 字段默认隐藏）。"""
    if key[0] == "lang":
        return key[1] in EDITABLE_NAME_IDS
    return True


# ---------------------------------------------------------------- 字重/字宽/斜体

# 字重为纯数值（编辑器用 spinbox 1-1000 编辑），不再有下拉项/标签映射。


def width_items() -> list[tuple[int, str]]:
    # 字宽列写死的简体枚举（与 WIDTH_LABELS 一致）
    return [(v, WIDTH_LABELS[v]) for v in sorted(WIDTH_LABELS)]


def format_width(value) -> str:
    return WIDTH_LABELS.get(value, str(value))


def format_italic(value) -> str:
    return "斜体" if value else "正常"


def parse_width(text) -> int | None:
    t = (text or "").strip()
    if not t:
        return None
    try:
        v = int(t)
        if v in WIDTH_LABELS:
            return v
    except ValueError:
        pass
    for v, lbl in WIDTH_LABELS.items():
        if t == lbl:
            return v
    return None


def parse_italic(text) -> bool:
    t = (text or "").strip()
    return t in ("斜体", "True", "true", "是", "1")
