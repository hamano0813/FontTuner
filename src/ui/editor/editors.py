"""表格内编辑器：解耦原始值与显示文本，供委托读写。"""

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QComboBox, QLineEdit, QWidget
from qfluentwidgets import isDarkTheme


class CellEditor(QWidget):
    """单元格编辑器基类——不调 super().__init__（与 QLineEdit/QComboBox 多继承时避免重复初始化）。"""

    dataChanged = Signal(object)

    def __init__(self, parent=None):
        self._value: Any = None

    # ---- 数据读写 ----

    def set_value(self, value) -> None:
        self._value = value
        self.format_value()

    def get_value(self) -> Any:
        return self._value

    # ---- 子类扩展点 ----

    def format_value(self) -> None:
        pass

    def apply_font(self, font: QFont) -> None:
        self.setFont(font)

    def apply_alignment(self, alignment) -> None:
        pass


class CellLineEdit(QLineEdit, CellEditor):
    """文本单元格编辑器。"""

    def __init__(self, parent=None):
        QLineEdit.__init__(self, parent)
        CellEditor.__init__(self, parent)
        self.setFrame(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setStyleSheet("background: transparent; padding-left: 8px; padding-right: 6px;")
        self.textChanged.connect(self._on_text_changed)

    def _text_color(self) -> QColor:
        return QColor(255, 255, 255) if isDarkTheme() else QColor(0, 0, 0)

    def paintEvent(self, e):
        palette = self.palette()
        palette.setColor(palette.ColorRole.Text, self._text_color())
        self.setPalette(palette)
        QLineEdit.paintEvent(self, e)

    def focusInEvent(self, e):
        super().focusInEvent(e)
        self.setCursorPosition(len(self.text()))

    def get_value(self) -> str:
        return self._value if self._value is not None else ""

    def format_value(self) -> None:
        self.blockSignals(True)
        self.setText(str(self._value) if self._value is not None else "")
        self.setCursorPosition(len(self.text()))
        self.blockSignals(False)

    def apply_font(self, font: QFont) -> None:
        self.setFont(font)

    def apply_alignment(self, alignment) -> None:
        self.setAlignment(alignment)

    def _on_text_changed(self, text: str) -> None:
        self._value = text
        self.dataChanged.emit(self._value)


class CellComboEditor(QComboBox, CellEditor):
    """下拉/可输入单元格编辑器。

    set_items 传入 [(value, label)]；选中项返回其 value，自由输入返回文本。
    """

    def __init__(self, parent=None):
        QComboBox.__init__(self, parent)
        CellEditor.__init__(self, parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setStyleSheet("background: transparent; padding-left: 8px; padding-right: 6px;")
        # 下拉列表保持实底，避免透明背景透出窗口
        dark = isDarkTheme()
        self.view().setStyleSheet(
            f"QAbstractItemView {{ background: {'#1f1f1f' if dark else '#ffffff'}; "
            f"color: {'#ffffff' if dark else '#1a1a1a'}; outline: none; }}"
        )

    def set_items(self, items: list[tuple[Any, str]]) -> None:
        self.blockSignals(True)
        self.clear()
        for value, label in items:
            self.addItem(label, value)
        self.blockSignals(False)

    def get_value(self) -> Any:
        idx = self.currentIndex()
        data = self.currentData()
        if idx >= 0 and data is not None:
            return data
        return self.currentText()

    def format_value(self) -> None:
        self.blockSignals(True)
        idx = self.findData(self._value)
        if idx >= 0:
            self.setCurrentIndex(idx)
        else:
            self.setEditText(str(self._value) if self._value is not None else "")
        self.blockSignals(False)

    def apply_font(self, font: QFont) -> None:
        self.setFont(font)

    def apply_alignment(self, alignment) -> None:
        if self.lineEdit() is not None:
            self.lineEdit().setAlignment(alignment)
