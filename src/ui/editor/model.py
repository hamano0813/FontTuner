"""字体表格模型：list[FontEntry] 逻辑字段 ↔ 单元格 的映射 + TSV 复制粘贴。"""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from core.models import FontEntry
from ui.editor.columns import (
    PLACEHOLDER_ROLE,
    ColumnDef,
    build_columns,
    format_italic,
    format_weight,
    format_width,
    parse_italic,
    parse_weight,
    parse_width,
)
from ui.signals import app_signals


class FontTableModel(QAbstractTableModel):
    valueChanged = Signal(int)   # 行号

    def __init__(self, parent=None):
        super().__init__(parent)
        self._columns: list[ColumnDef] = build_columns()
        self._entries: list[FontEntry] = []
        self._hints: dict[tuple, str] = {}

    def set_cell_hints(self, hints: dict[tuple, str]) -> None:
        """设置列级输入提示（模板版本号占位），空单元格以灰色提示显示。"""
        self._hints = dict(hints)
        if self._entries:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._entries) - 1, len(self._columns) - 1),
            )

    # ---------------------------------------------------------------- 数据源

    def set_entries(self, entries: list[FontEntry]) -> None:
        self.beginResetModel()
        self._entries = list(entries)
        self.endResetModel()

    def get_entries(self) -> list[FontEntry]:
        return self._entries

    def remove_rows(self, rows: list[int]) -> int:
        """从表格移除指定行（仅界面移除，不删文件，不再编辑）。返回移除行数。"""
        rows = sorted({r for r in rows if 0 <= r < len(self._entries)})
        if not rows:
            return 0
        self.beginResetModel()
        for i in reversed(rows):
            del self._entries[i]
        self.endResetModel()
        app_signals.project_edited.emit()
        return len(rows)

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

    # ---------------------------------------------------------------- Qt 接口

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._entries)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._columns[section].header
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if self._columns[index.column()].editable:
            base |= Qt.ItemFlag.ItemIsEditable
        return base

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._entries)):
            return None
        entry = self._entries[index.row()]
        col = self._columns[index.column()]
        value = self._get_value(entry, col.key)
        hint = self._hints.get(col.key) if col.kind == "text" else None
        showing_hint = bool(hint) and self._is_empty(value)
        if role == Qt.ItemDataRole.EditRole:
            return value
        if role == Qt.ItemDataRole.DisplayRole:
            if showing_hint:
                return hint
            return self._format(col, value)
        if role == Qt.ItemDataRole.ForegroundRole:
            if showing_hint:
                return QColor("#8a8a8a")
            return None
        if role == PLACEHOLDER_ROLE:
            return hint
        return None

    @staticmethod
    def _is_empty(value) -> bool:
        return value is None or str(value).strip() == ""

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        if not (0 <= index.row() < len(self._entries)):
            return False
        entry = self._entries[index.row()]
        col = self._columns[index.column()]
        if not col.editable:
            return False
        old = self._get_value(entry, col.key)
        parsed = self._parse(col, value)
        if parsed is None:
            return False
        self._set_value(entry, col.key, parsed)
        if old != parsed:
            self.valueChanged.emit(index.row())
            app_signals.project_edited.emit()
        self.dataChanged.emit(index, index, [role])
        return True

    # ---------------------------------------------------------------- 字段映射

    def _get_value(self, entry: FontEntry, key: tuple):
        kind = key[0]
        if kind == "fixed":
            tag = key[1]
            if tag == "fontPath":
                return entry.display_name()
            if tag == "weight":
                return entry.us_weight_class
            if tag == "width":
                return entry.us_width_class
            if tag == "italic":
                return entry.italic()
            if tag == "numGlyphs":
                return entry.num_glyphs
        if kind == "save":
            return entry.save_langs[key[1]]
        if kind == "temp":
            return entry.temp_names[key[1]]
        if kind == "charset":
            return entry.charsets[key[1]]
        if kind == "lang":
            return entry.names[key[1]][key[2]]
        return None

    def _set_value(self, entry: FontEntry, key: tuple, value):
        kind = key[0]
        if kind == "fixed":
            tag = key[1]
            if tag == "weight":
                entry.us_weight_class = value
            elif tag == "width":
                entry.us_width_class = value
            elif tag == "italic":
                entry.set_italic(value)
        elif kind == "save":
            entry.save_langs[key[1]] = bool(value)
        elif kind == "temp":
            entry.temp_names[key[1]] = str(value)
        elif kind == "charset":
            entry.charsets[key[1]] = str(value)
        elif kind == "lang":
            entry.names[key[1]][key[2]] = value

    def _format(self, col: ColumnDef, value) -> str:
        k = col.kind
        if k == "weight":
            return format_weight(value)
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
            return parse_weight(str(value))
        if k == "width":
            return parse_width(str(value))
        if k == "italic":
            return parse_italic(str(value))
        if k == "save":
            t = str(value).strip()
            return t in ("True", "true", "1", "是")
        return str(value)

    def _copy_text(self, col: ColumnDef, value) -> str:
        """单元格复制文本：组合列用标签，保存列用 True/False。"""
        k = col.kind
        if k == "save":
            return "True" if value else "False"
        if k == "italic":
            return format_italic(value)
        if k == "weight":
            return format_weight(value)
        if k == "width":
            return format_width(value)
        return "" if value is None else str(value)

    # ---------------------------------------------------------------- 复制粘贴

    def copy_selection(self, indexes) -> bool:
        if not indexes:
            return False
        rows = sorted({i.row() for i in indexes})
        cols = sorted({i.column() for i in indexes})
        if not rows or not cols:
            return False
        lines = []
        for r in rows:
            if r >= len(self._entries):
                continue
            entry = self._entries[r]
            cells = []
            for c in cols:
                col = self._columns[c]
                cells.append(self._copy_text(col, self._get_value(entry, col.key)))
            lines.append("\t".join(cells))
        QApplication.clipboard().setText("\n".join(lines))
        return True

    def paste_at(self, row: int, col: int) -> int:
        text = QApplication.clipboard().text()
        if not text or not text.strip():
            return 0
        lines = text.strip().split("\n")
        count = 0
        for li, line in enumerate(lines):
            if not line.strip():
                continue
            cells = line.split("\t")
            for ci, cell in enumerate(cells):
                r, c = row + li, col + ci
                if r >= len(self._entries) or c >= len(self._columns):
                    continue
                if self.setData(self.index(r, c), cell, Qt.ItemDataRole.EditRole):
                    count += 1
        return count

    def delete_selection(self, indexes) -> bool:
        if not indexes:
            return False
        for idx in indexes:
            if idx.row() >= len(self._entries):
                continue
            col = self._columns[idx.column()]
            if not col.editable:
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
