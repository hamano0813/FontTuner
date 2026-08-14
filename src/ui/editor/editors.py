"""表格内编辑器：解耦原始值与显示文本，供委托读写。"""

from typing import Any

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import QComboBox, QLineEdit, QSizePolicy, QSpinBox, QToolButton, QWidget
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
    editable=False 时为纯下拉（如字宽列，禁止输入文字，只能选择）。
    """

    def __init__(self, parent=None, editable: bool = True):
        QComboBox.__init__(self, parent)
        CellEditor.__init__(self, parent)
        self.setEditable(editable)
        if editable:
            self.lineEdit().setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)  # 输入框禁用右键菜单
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
                "color: white; outline: none; padding-left: 10px; }"
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
                "color: black; outline: none; padding-left: 10px; }"
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


class _SpinArrow(QToolButton):
    """左右箭头按钮：左箭头递减、右箭头递增（srw CellNumberStepper 同款自绘）。"""

    def __init__(self, right: bool, parent=None):
        super().__init__(parent)
        self._right = right
        self.setFixedSize(20, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, e):
        parent = self.parent()
        if self._right:
            parent.stepUp()
        else:
            parent.stepDown()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(200, 200, 200) if isDarkTheme() else QColor(80, 80, 80))
        s = 5
        cx, cy = self.width() / 2, self.height() / 2
        path = QPainterPath()
        if self._right:
            path.moveTo(QPointF(cx + s, cy))
            path.lineTo(QPointF(cx - s, cy - s))
            path.lineTo(QPointF(cx - s, cy + s))
        else:
            path.moveTo(QPointF(cx - s, cy))
            path.lineTo(QPointF(cx + s, cy - s))
            path.lineTo(QPointF(cx + s, cy + s))
        path.closeSubpath()
        painter.drawPath(path)


class CellSpinBox(QSpinBox, CellEditor):
    """数值单元格编辑器（字重 1-1000）：透明无边框 + 自绘左右箭头按钮（srw 同款）。

    左减右加按钮步进、键盘可直接输入数值；set_value 传入整数值，get_value 返回编辑后数值。
    """

    def __init__(self, parent=None, minimum: int = 1, maximum: int = 1000):
        QSpinBox.__init__(self, parent)
        CellEditor.__init__(self, parent)
        self.setFrame(False)
        self.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)  # 用自绘左右箭头
        self.setRange(minimum, maximum)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setStyleSheet(
            "QSpinBox { background: transparent; border: none; }"
        )
        # 文字颜色直接设在内部 lineEdit（QSpinBox 文本由它绘制），随主题明暗
        le = self.lineEdit()
        le.setFrame(False)
        le.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        le.setAlignment(Qt.AlignmentFlag.AlignCenter)
        le.setStyleSheet(
            "background: transparent; border: none; color: #FFFFFF;"
            if isDarkTheme() else
            "background: transparent; border: none; color: #000000;"
        )
        self._btn_left = _SpinArrow(False, self)
        self._btn_right = _SpinArrow(True, self)
        self.valueChanged.connect(self._on_value_changed)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        bw = self._btn_left.width()
        y = (self.height() - self._btn_left.height()) // 2
        self._btn_left.move(1, y)
        self._btn_right.move(self.width() - bw - 1, y)

    def focusInEvent(self, e):
        super().focusInEvent(e)
        self.selectAll()

    def get_value(self) -> int:
        # 以 spinbox 当前值（含用户编辑）为准，避免 _value 滞后于未提交的输入
        return self.value()

    def format_value(self) -> None:
        self.blockSignals(True)
        self.setValue(self._value if self._value is not None else self.minimum())
        self.blockSignals(False)

    def apply_font(self, font: QFont) -> None:
        self.setFont(font)

    def apply_alignment(self, alignment) -> None:
        self.setAlignment(alignment)

    def _on_value_changed(self, v: int) -> None:
        self._value = v
        self.dataChanged.emit(self._value)
