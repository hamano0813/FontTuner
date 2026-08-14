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
from ui.editor.editors import CellComboEditor, CellLineEdit, CellSpinBox

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

    def _is_structural_empty(self, index: QModelIndex) -> bool:
        """结构空单元格：父行×子列 / 子行×父列，不绘制芯片底色。

        树形下父节点只填父列、子节点只填子列，对方类型列恒为空白。
        """
        model = index.model()
        if model is None or not hasattr(model, "node_of") or not hasattr(model, "column_key"):
            return False
        is_parent_node = model.node_of(index) == 0
        is_parent_col = model.column_key(index.column())[0] == "fixed"
        return is_parent_node != is_parent_col

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        if self._is_structural_empty(index):
            return  # 不绘制芯片，留白
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


class SpinDelegate(BaseCellDelegate):
    """数值单元格委托（字重 1-1000 数值直编，无下拉）。"""
    widget_class = CellSpinBox


class ComboDelegate(BaseCellDelegate):
    widget_class = CellComboEditor

    def __init__(self, items, parent=None, editable: bool = True):
        super().__init__(parent)
        self._items = list(items)
        self._editable = editable

    def createEditor(self, parent: QWidget, option, index: QModelIndex) -> QWidget:
        editor = CellComboEditor(parent, editable=self._editable)
        self._apply_editor_font(editor)
        editor.set_items(self._items)
        return editor


class ReadOnlyDelegate(BaseCellDelegate):
    widget_class = None


def _centered_checkbox_rect(rect: QRect) -> QRect:
    """居中勾选框：以样式实际指示器尺寸（SE_CheckBoxIndicator）为准。

    PM_IndicatorWidth/Height 可能与 CE_CheckBox 实际绘制尺寸不一致（尤其跨平台/样式），
    用 subElementRect 取真实指示器矩形，再按它的宽高居中，避免勾选框偏移。
    """
    opt = QStyleOptionButton()
    opt.rect = rect
    ind = QApplication.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, opt)
    w, h = ind.width(), ind.height()
    # 居中的基础上整体左移 4px（斜体格勾选框的视觉微调）
    x = rect.x() + (rect.width() - w) // 2 - 4
    y = rect.y() + (rect.height() - h) // 2
    return QRect(x, y, w, h)


class CheckBoxDelegate(BaseCellDelegate):
    """复选列委托：芯片底 + 居中勾选框，原地点击切换。"""

    widget_class = None

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        if self._is_structural_empty(index):
            return  # 子行×父列（斜体）留白
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


class SaveLangDelegate(BaseCellDelegate):
    """保存列委托：芯片底 + 居中「复选框 + 语言标签（简/繁/日/英）」，点击切换保存开关。"""

    widget_class = None

    def _text_color(self) -> QColor:
        return QColor(255, 255, 255) if isDarkTheme() else QColor(0, 0, 0)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        if self._is_structural_empty(index):
            return  # 父行×保存列留白
        self._paint_chip_background(painter, option, index)
        checked = index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        rect = option.rect
        style = QApplication.style()
        indicator = style.pixelMetric(QStyle.PixelMetric.PM_IndicatorWidth)
        fm = QFontMetrics(getFont(13))
        text_w = fm.horizontalAdvance(text)
        gap = 8
        total = indicator + gap + text_w
        x = rect.x() + (rect.width() - total) // 2
        cy = rect.y() + rect.height() // 2
        opt = QStyleOptionButton()
        opt.rect = QRect(x, cy - indicator // 2, indicator, indicator)
        opt.state = QStyle.StateFlag.State_Enabled
        opt.state |= QStyle.StateFlag.State_On if checked else QStyle.StateFlag.State_Off
        style.drawControl(QStyle.ControlElement.CE_CheckBox, opt, painter, option.widget)
        painter.setFont(getFont(13))
        painter.setPen(self._text_color())
        painter.drawText(
            QRect(x + indicator + gap, rect.y(), text_w, rect.height()),
            Qt.AlignmentFlag.AlignVCenter, text,
        )

    def editorEvent(self, event, model, option, index: QModelIndex) -> bool:
        if (
            event.type() == QEvent.Type.MouseButtonRelease
            and index.isValid()
            and index.flags() & Qt.ItemFlag.ItemIsEditable
        ):
            checked = index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
            model.setData(index, not checked, Qt.ItemDataRole.EditRole)
            return True
        return False
