"""表格内编辑器：解耦原始值与显示文本，供委托读写。"""

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QComboBox, QLineEdit, QSizePolicy, QWidget
from qfluentwidgets import ScrollBar, isDarkTheme


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
    """下拉/可输入单元格编辑器（VAS 主题化：透明背景 + 圆角下拉 + qfw ScrollBar）。

    set_items 传入 [(value, label)]；选中项返回其 value，自由输入返回文本。
    """

    def __init__(self, parent=None):
        QComboBox.__init__(self, parent)
        CellEditor.__init__(self, parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setCompleter(None)
        self.setMaxVisibleItems(10)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFrame(False)
        self._apply_theme()
        self._view_styled = False

    # ========== VAS 主题化 QSS ==========

    def _apply_theme(self) -> None:
        if isDarkTheme():
            qss = (
                "QComboBox { border: none; border-radius: 0px; background: transparent; "
                "color: white; outline: none; }"
                "QComboBox:hover { border: none; background: transparent; }"
                "QComboBox:focus { border: none; background: transparent; }"
                "QComboBox::drop-down { width: 20px; border: none; background: transparent; }"
                "QComboBox::down-arrow {"
                "  image: url(:/qfluentwidgets/images/icons/ChevronDown_white.svg);"
                "  width: 10px; height: 10px;"
                "}"
                "QComboBox QAbstractItemView {"
                "  border: 1px solid rgba(255,255,255,0.08); border-radius: 5px;"
                "  background: rgba(40,40,40,0.95); color: white; padding: 6px 8px; outline: none;"
                "}"
                "QComboBox QAbstractItemView::item {"
                "  min-height: 28px; padding: 2px 12px; margin: 2px 0;"
                "}"
                "QComboBox QAbstractItemView::item:hover {"
                "  background: rgba(255,255,255,0.08); border-radius: 5px;"
                "}"
                "QComboBox QAbstractItemView::item:selected {"
                "  background: rgba(96, 165, 250, 0.25); color: white; border-radius: 5px;"
                "}"
                "QComboBox QListView { border-radius: 5px; }"
            )
            line_edit_qss = "background: transparent; border: none; padding-left: 8px; color: white;"
        else:
            qss = (
                "QComboBox { border: none; border-radius: 0px; background: transparent; "
                "color: black; outline: none; }"
                "QComboBox:hover { border: none; background: transparent; }"
                "QComboBox:focus { border: none; background: transparent; }"
                "QComboBox::drop-down { width: 20px; border: none; background: transparent; }"
                "QComboBox::down-arrow {"
                "  image: url(:/qfluentwidgets/images/icons/ChevronDown_black.svg);"
                "  width: 10px; height: 10px;"
                "}"
                "QComboBox QAbstractItemView {"
                "  border: 1px solid rgba(0,0,0,0.1); border-radius: 5px;"
                "  background: white; color: black; padding: 6px 8px; outline: none;"
                "}"
                "QComboBox QAbstractItemView::item {"
                "  min-height: 28px; padding: 2px 12px; margin: 2px 0;"
                "}"
                "QComboBox QAbstractItemView::item:hover {"
                "  background: rgba(0,0,0,0.04); border-radius: 5px;"
                "}"
                "QComboBox QAbstractItemView::item:selected {"
                "  background: rgba(74, 158, 255, 0.2); color: black; border-radius: 5px;"
                "}"
                "QComboBox QListView { border-radius: 5px; }"
            )
            line_edit_qss = "background: transparent; border: none; padding-left: 8px; color: black;"
        self.setStyleSheet(qss)
        if self.lineEdit() is not None:
            self.lineEdit().setStyleSheet(line_edit_qss)

    # ========== 下拉视图：qfw 圆角滚动条 ==========

    def showPopup(self) -> None:
        if not self._view_styled:
            view = self.view()
            if view is not None:
                view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                super().showPopup()
                sb = ScrollBar(Qt.Orientation.Vertical, view)
                sb.setRange(sb.partnerBar.minimum(), sb.partnerBar.maximum())
                sb.setVisible(sb.maximum() > 0)
                sb._isEnter = True
                sb.expand()
                sb._isEnter = False
                sb.collapse()
                self._view_styled = True
                return
        super().showPopup()

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
