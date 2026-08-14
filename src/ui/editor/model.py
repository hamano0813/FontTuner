"""字体树形模型：每个字体 = 父节点，4 个语言（简/繁/日/英）= 4 个子节点。

internalId = font_idx*5 + node（0=父节点，1..4=LANGS 下标+1）。父行只填父列
（模板/字重/字宽…），子行只填子列（保存/字体名/字符集/语言字段），对方列空且不可编辑。
"""

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from core.models import FontEntry, LANG_PREFIX, LANGS
from ui.editor.columns import (
    PLACEHOLDER_ROLE,
    ColumnDef,
    build_columns,
    format_italic,
    format_width,
    parse_italic,
    parse_width,
)
from ui.signals import app_signals


def _is_parent_node(node: int) -> bool:
    return node == 0


class FontTreeModel(QAbstractItemModel):
    valueChanged = Signal(int)   # 字体序号（预览联动用）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._columns: list[ColumnDef] = build_columns()
        self._entries: list[FontEntry] = []
        self._hints: dict[tuple, str] = {}

    def set_cell_hints(self, hints: dict[tuple, str]) -> None:
        """设置列级输入提示（模板版本号占位），空单元格以灰色提示显示。"""
        self._hints = dict(hints)
        if self._entries:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._entries) - 1, 0))

    # ---------------------------------------------------------------- 数据源

    def set_entries(self, entries: list[FontEntry]) -> None:
        self.beginResetModel()
        self._entries = list(entries)
        self.endResetModel()

    def get_entries(self) -> list[FontEntry]:
        return self._entries

    def remove_fonts(self, font_indices: list[int]) -> int:
        """按字体序号从表格移除（仅界面移除，不删文件）。返回移除字体数。"""
        indices = sorted({i for i in font_indices if 0 <= i < len(self._entries)})
        if not indices:
            return 0
        self.beginResetModel()
        for i in reversed(indices):
            del self._entries[i]
        self.endResetModel()
        app_signals.project_edited.emit()
        return len(indices)

    @property
    def columns(self) -> list[ColumnDef]:
        return self._columns

    def column_key(self, col: int) -> tuple:
        return self._columns[col].key

    def column_index(self, key: tuple) -> int:
        for i, c in enumerate(self._columns):
            if c.key == key:
                return i
        return -1

    # ---------------------------------------------------------------- 树形索引

    def font_of(self, index: QModelIndex) -> int:
        """任一 index 所属字体序号；无效返回 -1。"""
        return index.internalId() // 5 if index.isValid() else -1

    def node_of(self, index: QModelIndex) -> int:
        """节点序号：0=父节点，1..4=LANGS 对应语言。"""
        return index.internalId() % 5 if index.isValid() else -1

    def lang_of(self, index: QModelIndex) -> str | None:
        """子节点对应的语言；父节点返回 None。"""
        node = self.node_of(index)
        return None if _is_parent_node(node) else LANGS[node - 1]

    def _index_node(self, font_idx: int, node: int, col: int) -> QModelIndex:
        """构造指定 (字体, 节点, 列) 的 QModelIndex（供粘贴等内部使用）。"""
        if not (0 <= font_idx < len(self._entries)):
            return QModelIndex()
        internal = font_idx * 5 + node
        if _is_parent_node(node):
            return self.createIndex(font_idx, col, internal)
        return self.createIndex(node - 1, col, internal)

    # ---------------------------------------------------------------- Qt 接口

    def rowCount(self, parent=QModelIndex()) -> int:
        if not parent.isValid():
            return len(self._entries)
        if _is_parent_node(parent.internalId() % 5):
            return 4
        return 0

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._columns)

    def hasChildren(self, parent=QModelIndex()) -> bool:
        if not parent.isValid():
            return len(self._entries) > 0
        return _is_parent_node(parent.internalId() % 5)

    def index(self, row, col, parent=QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, col, parent):
            return QModelIndex()
        if not parent.isValid():
            if 0 <= row < len(self._entries):
                return self.createIndex(row, col, row * 5)  # 父节点
            return QModelIndex()
        if _is_parent_node(parent.internalId() % 5) and 0 <= row < 4:
            return self.createIndex(row, col, parent.internalId() + (row + 1))  # 子节点
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid() or _is_parent_node(index.internalId() % 5):
            return QModelIndex()
        font_idx = index.internalId() // 5
        return self.createIndex(font_idx, 0, font_idx * 5)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Orientation.Horizontal:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return self._columns[section].header
        if role == Qt.ItemDataRole.ToolTipRole:
            en = self._columns[section].en
            return f"{self._columns[section].header} · {en}" if en else None
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        col = self._columns[index.column()]
        if not col.editable:
            return base
        # 父节点只可编辑父列；子节点只可编辑子列
        if _is_parent_node(self.node_of(index)) == (col.key[0] == "fixed"):
            base |= Qt.ItemFlag.ItemIsEditable
        return base

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        font_idx = self.font_of(index)
        node = self.node_of(index)
        if not (0 <= font_idx < len(self._entries)):
            return None
        entry = self._entries[font_idx]
        col = self._columns[index.column()]
        key = col.key
        if _is_parent_node(node):
            if key[0] != "fixed":
                return None  # 父行子列空
            lang = None
        else:
            if key[0] == "fixed":
                return None  # 子行父列空
            lang = LANGS[node - 1]
        # 字重列数值居中、字形数右对齐（其余列左对齐）
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if key == ("fixed", "weight"):
                return Qt.AlignmentFlag.AlignCenter
            if key == ("fixed", "numGlyphs"):
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        value = self._get_value(entry, key, lang)
        # 保存列：显示语言标签 + 勾选状态
        if key[0] == "save":
            if role == Qt.ItemDataRole.EditRole:
                return value
            if role == Qt.ItemDataRole.DisplayRole:
                return LANG_PREFIX[lang]
            if role == Qt.ItemDataRole.CheckStateRole:
                return Qt.CheckState.Checked if value else Qt.CheckState.Unchecked
            return None
        hint = self._hints.get(key) if col.kind == "text" else None
        showing_hint = bool(hint) and self._is_empty(value)
        if role == Qt.ItemDataRole.EditRole:
            return value
        if role == Qt.ItemDataRole.DisplayRole:
            if showing_hint:
                return hint
            return self._format(col, value)
        if role == Qt.ItemDataRole.ForegroundRole:
            return QColor("#8a8a8a") if showing_hint else None
        if role == PLACEHOLDER_ROLE:
            return hint
        return None

    @staticmethod
    def _is_empty(value) -> bool:
        return value is None or str(value).strip() == ""

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        if not (self.flags(index) & Qt.ItemFlag.ItemIsEditable):
            return False
        font_idx = self.font_of(index)
        entry = self._entries[font_idx]
        col = self._columns[index.column()]
        lang = self.lang_of(index)
        old = self._get_value(entry, col.key, lang)
        parsed = self._parse(col, value)
        if parsed is None:
            return False
        self._set_value(entry, col.key, parsed, lang)
        if old != parsed:
            self.valueChanged.emit(font_idx)
            app_signals.project_edited.emit()
        self.dataChanged.emit(index, index, [role])
        return True

    # ---------------------------------------------------------------- 字段映射

    def _get_value(self, entry: FontEntry, key: tuple, lang: str | None = None):
        kind = key[0]
        if kind == "fixed":
            tag = key[1]
            if tag == "fontPath":
                return entry.display_name()
            if tag == "templateName":
                return entry.template_name
            if tag == "renameTemplate":
                return entry.rename_template
            if tag == "weight":
                return entry.us_weight_class
            if tag == "width":
                return entry.us_width_class
            if tag == "italic":
                return entry.italic()
            if tag == "numGlyphs":
                return entry.num_glyphs
        if lang is None:
            return None
        if kind == "save":
            return entry.save_langs[lang]
        if kind == "temp":
            return entry.temp_names[lang]
        if kind == "charset":
            return entry.charsets[lang]
        if kind == "lang":
            return entry.names[lang][key[1]]
        return None

    def _set_value(self, entry: FontEntry, key: tuple, value, lang: str | None = None) -> None:
        kind = key[0]
        if kind == "fixed":
            tag = key[1]
            if tag == "weight":
                entry.us_weight_class = value
            elif tag == "width":
                entry.us_width_class = value
            elif tag == "italic":
                entry.set_italic(value)
            elif tag == "renameTemplate":
                entry.rename_template = str(value)
            elif tag == "templateName":
                entry.template_name = str(value)
        elif lang is not None:
            if kind == "save":
                entry.save_langs[lang] = bool(value)
            elif kind == "temp":
                entry.temp_names[lang] = str(value)
            elif kind == "charset":
                entry.charsets[lang] = str(value)
            elif kind == "lang":
                entry.names[lang][key[1]] = value

    def _format(self, col: ColumnDef, value) -> str:
        k = col.kind
        if k == "weight":
            return "" if value is None else str(value)
        if k == "width":
            return format_width(value)
        if k == "italic":
            return format_italic(value)
        if k == "save":
            return ""
        return "" if value is None else str(value)

    def _parse(self, col: ColumnDef, value):
        """把委托传来的文本/值解析为存储值；无法解析返回 None（拒绝写回）。"""
        k = col.kind
        if k == "weight":
            try:
                v = int(str(value).strip())
            except ValueError:
                return None
            return v if 1 <= v <= 1000 else None
        if k == "width":
            return parse_width(str(value))
        if k == "italic":
            return parse_italic(str(value))
        if k == "save":
            t = str(value).strip()
            return t in ("True", "true", "1", "是")
        return str(value)

    def _copy_text(self, col: ColumnDef, value) -> str:
        """单元格复制文本：组合列用标签，保存列用 True/False；None（对方类型列）复制为空串。"""
        k = col.kind
        if value is None:
            return ""
        if k == "save":
            return "True" if value else "False"
        if k == "italic":
            return format_italic(value)
        if k == "weight":
            return str(value)
        if k == "width":
            return format_width(value)
        return str(value)

    # ---------------------------------------------------------------- 复制粘贴（按视觉行）

    def copy_selection(self, indexes) -> bool:
        """把选中的视觉行（父行或子行）复制为 TSV：只含选中列，对方类型列留空。

        只复制被选中的列：单选某格只复制该格，跨列多选复制所选各列，整行/整字体
        全选才整行复制。粘贴按列位置对齐，未选列留空不会被写入——避免「复制字符集
        却把同行的字体名/家族名一起带过去」。
        """
        if not indexes:
            return False
        rows: dict[tuple[int, int], None] = {}
        selected_cols: set[int] = set()
        for idx in indexes:
            if not idx.isValid():
                continue
            rows.setdefault((self.font_of(idx), self.node_of(idx)), None)
            selected_cols.add(idx.column())
        if not rows:
            return False
        lines = []
        for font_idx, node in sorted(rows):
            entry = self._entries[font_idx]
            lang = None if _is_parent_node(node) else LANGS[node - 1]
            cells = []
            for ci, col in enumerate(self._columns):
                if ci not in selected_cols:
                    cells.append("")  # 未选列留空，粘贴不写入
                    continue
                valid = _is_parent_node(node) == (col.key[0] == "fixed")
                value = self._get_value(entry, col.key, lang) if valid else None
                cells.append(self._copy_text(col, value))
            lines.append("\t".join(cells))
        QApplication.clipboard().setText("\n".join(lines))
        return True

    def paste_at(self, index, col: int) -> int:
        """以目标视觉行为起点，把剪贴板逐行写入连续视觉行（按视觉行递进）。

        保留行首/行尾空 Tab（子行前 7 个父列空），空单元格不覆盖（避免跨类型
        粘贴误清值）；不可编辑格由 setData 自动跳过。视觉行 = 字体序号×5 + 节点序号，
        整字体复制（父+4子）粘贴到父行可整体回填。
        """
        text = QApplication.clipboard().text()
        if not text:
            return 0
        lines = [ln.rstrip("\r") for ln in text.split("\n") if ln.strip()]
        if not lines:
            return 0
        start_visual = self.font_of(index) * 5 + self.node_of(index)
        if start_visual < 0:
            return 0
        count = 0
        for li, line in enumerate(lines):
            font_idx, node = divmod(start_visual + li, 5)
            if font_idx >= len(self._entries):
                break
            for ci, cell in enumerate(line.split("\t")):
                if ci >= len(self._columns):
                    break
                if not cell.strip():
                    continue
                if self.setData(self._index_node(font_idx, node, ci), cell,
                                Qt.ItemDataRole.EditRole):
                    count += 1
        return count

    def delete_selection(self, indexes) -> bool:
        if not indexes:
            return False
        for idx in indexes:
            if not idx.isValid():
                continue
            col = self._columns[idx.column()]
            if not (self.flags(idx) & Qt.ItemFlag.ItemIsEditable):
                continue
            if col.kind == "text":
                self.setData(idx, "", Qt.ItemDataRole.EditRole)
            elif col.kind == "italic":
                self.setData(idx, "正常", Qt.ItemDataRole.EditRole)
            elif col.kind == "save":
                self.setData(idx, False, Qt.ItemDataRole.EditRole)
            elif col.kind == "weight":
                self.setData(idx, "400", Qt.ItemDataRole.EditRole)
            elif col.kind == "width":
                self.setData(idx, "5", Qt.ItemDataRole.EditRole)
        return True
