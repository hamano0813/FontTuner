"""单元格委托（VAS DataWidgetDelegate 移植）：芯片式自绘悬浮/选中态 + 各类编辑器。

qfw TableView 默认 TableItemDelegate 的整行绘制会被按列挂的自定义 delegate 取代，
因此在 paint() 里自行绘制圆角芯片底（普通/悬浮/选中三态），恢复 qfw 的视觉特效。
"""

from typing import Any

from PySide6.QtCore import QEvent, QModelIndex, QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPalette
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionButton, QStyledItemDelegate, QStyleOptionViewItem, QWidget
from qfluentwidgets import getFont, isDarkTheme, setFont

from ui.editor.columns import PLACEHOLDER_ROLE
from ui.editor.editors import CellComboEditor, CellLineEdit

# 芯片式单元格参数：格间缝隙 / 圆角半径 / 文字内边距
_CHIP_GAP = 2
_CHIP_RADIUS = 5
_CHIP_PAD = 8

# 半透明芯片配色（亮/暗）：普通 / 悬停 / 选中（#AARRGGBB，随 Mica 背景色调漂移）
_CHIP_COLORS = {
    True: {"normal": "#08FFFFFF", "hover": "#10FFFFFF", "selected": "#1EFFFFFF"},
    False: {"normal": "#06000000", "hover": "#0C000000", "selected": "#18000000"},
}


class BaseCellDelegate(QStyledItemDelegate):
    """芯片式单元格委托基类：createEditor/setEditorData/setModelData 已实现。

    子类覆盖 widget_class 指定编辑器；widget_class=None 为只读列。
    """

    widget_class: type | None = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editing_index: QModelIndex | None = None

    # ---------------------------------------------------------------- 绘制

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        if self._editing_index is not None and index == self._editing_index:
            self._paint_chip_background(painter, option, index)
            return
        self._paint_chip(painter, option, index)

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        super().initStyleOption(option, index)
        option.font = index.data(Qt.ItemDataRole.FontRole) or getFont(13)
        text_color = Qt.GlobalColor.white if isDarkTheme() else Qt.GlobalColor.black
        brush = index.data(Qt.ItemDataRole.ForegroundRole)
        if brush is not None:
            text_color = QColor(brush).name() if not isinstance(brush, QColor) else brush
        option.palette.setColor(QPalette.ColorRole.Text, text_color)
        option.palette.setColor(QPalette.ColorRole.HighlightedText, text_color)

    def _chip_color(self, option: QStyleOptionViewItem) -> QColor:
        colors = _CHIP_COLORS[isDarkTheme()]
        if option.state & QStyle.StateFlag.State_Selected:
            return QColor(colors["selected"])
        if option.state & QStyle.StateFlag.State_MouseOver:
            return QColor(colors["hover"])
        return QColor(colors["normal"])

    def _chip_bg_color(self, option: QStyleOptionViewItem, index: QModelIndex) -> QColor:
        if not (option.state & QStyle.StateFlag.State_Selected):
            bg = index.data(Qt.ItemDataRole.BackgroundRole)
            if bg is not None:
                return QColor(bg)
        return self._chip_color(option)

    def _chip_rect(self, option: QStyleOptionViewItem) -> QRect:
        return option.rect.adjusted(_CHIP_GAP, _CHIP_GAP, -_CHIP_GAP, -_CHIP_GAP)

    def _paint_chip(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        rect = self._chip_rect(option)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._chip_bg_color(option, index))
        painter.drawRoundedRect(rect, _CHIP_RADIUS, _CHIP_RADIUS)

        text = str(opt.text) if opt.text is not None else ""
        if text:
            painter.setFont(opt.font)
            painter.setPen(opt.palette.color(QPalette.ColorRole.Text))
            text_rect = rect.adjusted(_CHIP_PAD, 0, -_CHIP_PAD, 0)
            if text_rect.width() > 0:
                fm = QFontMetrics(opt.font)
                elided = fm.elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width())
                painter.drawText(text_rect, int(opt.displayAlignment), elided)
        painter.restore()

    def _paint_chip_background(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._chip_bg_color(option, index))
        painter.drawRoundedRect(self._chip_rect(option), _CHIP_RADIUS, _CHIP_RADIUS)
        painter.restore()

    # ---------------------------------------------------------------- 编辑器

    def createEditor(self, parent: QWidget, option, index: QModelIndex) -> QWidget | None:
        if self.widget_class is None:
            return None
        editor = self.widget_class(parent)
        self._apply_editor_font(editor)
        return editor

    def _apply_editor_font(self, editor: QWidget) -> None:
        """编辑器与表格同字号（像素 13）；可编辑下拉还要同步内部输入框，
        否则 lineEdit 保持系统默认字号，比表格小一号。"""
        setFont(editor, 13)
        le = editor.lineEdit() if hasattr(editor, "lineEdit") else None
        if le is not None:
            setFont(le, 13)

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:
        self._editing_index = index
        editor.set_value(index.data(Qt.ItemDataRole.EditRole))
        alignment = index.data(Qt.ItemDataRole.TextAlignmentRole)
        if alignment is not None:
            editor.apply_alignment(alignment)

    def setModelData(self, editor: QWidget, model, index: QModelIndex) -> None:
        model.setData(index, editor.get_value(), Qt.ItemDataRole.EditRole)
        self._editing_index = None

    def destroyEditor(self, editor: QWidget, index: QModelIndex) -> None:
        self._editing_index = None
        super().destroyEditor(editor, index)

    def updateEditorGeometry(self, editor: QWidget, option, index: QModelIndex) -> None:
        editor.setGeometry(option.rect)

    # ---------------------------------------------------------------- qfw 兼容（no-op）

    def setHoverRow(self, row: int) -> None:
        pass

    def setPressedRow(self, row: int) -> None:
        pass

    def setSelectedRows(self, indexes) -> None:
        pass

    def setCheckedColor(self, light, dark) -> None:
        pass


class TextDelegate(BaseCellDelegate):
    widget_class = CellLineEdit

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:
        super().setEditorData(editor, index)
        hint = index.data(PLACEHOLDER_ROLE)
        if hint:
            editor.setPlaceholderText(hint)


class ComboDelegate(BaseCellDelegate):
    widget_class = CellComboEditor

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self._items = list(items)

    def createEditor(self, parent: QWidget, option, index: QModelIndex) -> QWidget:
        editor = CellComboEditor(parent)
        self._apply_editor_font(editor)
        editor.set_items(self._items)
        return editor


class ReadOnlyDelegate(BaseCellDelegate):
    widget_class = None


def _centered_checkbox_rect(rect: QRect) -> QRect:
    indicator = QApplication.style().pixelMetric(QStyle.PixelMetric.PM_IndicatorWidth)
    x = rect.x() + (rect.width() - indicator) // 2
    y = rect.y() + (rect.height() - indicator) // 2
    return QRect(x, y, indicator, indicator)


class CheckBoxDelegate(BaseCellDelegate):
    """复选列委托：芯片底 + 居中勾选框，原地点击切换。"""

    widget_class = None

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        self._paint_chip_background(painter, option, index)
        opt = QStyleOptionButton()
        opt.rect = _centered_checkbox_rect(option.rect)
        opt.state = QStyle.StateFlag.State_Enabled
        opt.state |= (
            QStyle.StateFlag.State_On if index.data(Qt.ItemDataRole.EditRole) else QStyle.StateFlag.State_Off
        )
        QApplication.style().drawControl(QStyle.ControlElement.CE_CheckBox, opt, painter, option.widget)

    def editorEvent(self, event, model, option, index: QModelIndex) -> bool:
        if (
            event.type() == QEvent.Type.MouseButtonRelease
            and index.isValid()
            and index.flags() & Qt.ItemFlag.ItemIsEditable
        ):
            model.setData(index, not bool(index.data(Qt.ItemDataRole.EditRole)), Qt.ItemDataRole.EditRole)
            return True
        return False
