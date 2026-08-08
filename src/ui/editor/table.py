"""字体表格视图：qfw TableView + 复制粘贴删除 + 语言列显隐。"""

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QContextMenuEvent, QKeyEvent, QKeySequence
from PySide6.QtWidgets import QTableView
from qfluentwidgets import Action, FluentIcon as FIF, RoundMenu, TableView, setCustomStyleSheet
from qfluentwidgets.common.smooth_scroll import SmoothMode

from core.models import EDITABLE_NAME_IDS, LANGS

_DEFAULT_WIDTHS = {
    ("fixed", "fontPath"): 220,
    ("fixed", "weight"): 80,
    ("fixed", "width"): 80,
    ("fixed", "italic"): 70,
    ("fixed", "numGlyphs"): 66,
}


class FontTableView(TableView):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self._model = model
        self.setModel(model)

        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setSelectionMode(QTableView.SelectionMode.ContiguousSelection)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectItems)
        self.setAlternatingRowColors(False)
        self.verticalHeader().setVisible(False)  # 不显示行号列
        self.horizontalHeader().setHighlightSections(False)

        # 关闭 qfw 平滑滚动（高行数表格 60fps 插值重绘很卡），回退到原生滚动
        self.scrollDelagate.verticalSmoothScroll.setSmoothMode(SmoothMode.NO_SMOOTH)
        self.scrollDelagate.horizonSmoothScroll.setSmoothMode(SmoothMode.NO_SMOOTH)

        # 语言组/额外字段显隐状态
        self._lang_visible = {lang: True for lang in LANGS}
        self._show_extra = False

        self._init_width()
        self._init_style()
        self._refresh_column_visibility()

    # ---------------------------------------------------------------- 键盘

    def keyPressEvent(self, e: QKeyEvent):
        if e.matches(QKeySequence.StandardKey.Copy):
            self._copy()
        elif e.matches(QKeySequence.StandardKey.Paste):
            self._paste()
        elif e.key() == Qt.Key.Key_Delete:
            self._delete()
        else:
            super().keyPressEvent(e)

    def _copy(self):
        indexes = self.selectionModel().selectedIndexes()
        if indexes:
            self._model.copy_selection(set(indexes))

    def _paste(self):
        idx = self.currentIndex()
        if idx.isValid():
            self._model.paste_at(idx.row(), idx.column())

    def _delete(self):
        indexes = self.selectionModel().selectedIndexes()
        if indexes:
            self._model.delete_selection(set(indexes))

    # ---------------------------------------------------------------- 右键菜单

    def contextMenuEvent(self, e: QContextMenuEvent):
        menu = RoundMenu(self)
        del_action = Action(FIF.DELETE, "删除选中字体")
        del_action.triggered.connect(self._remove_selected_rows)
        menu.addAction(del_action)
        menu.exec(e.globalPos())
        e.accept()

    def _remove_selected_rows(self):
        """从界面移除选中的整行字体（不删文件，仅不再编辑）。"""
        selection = self.selectionModel()
        rows = sorted({i.row() for i in selection.selectedIndexes()})
        if not rows:
            return
        removed = self._model.remove_rows(rows)
        if removed and self._model.rowCount() > 0:
            col = self.currentIndex().column() if self.currentIndex().isValid() else 0
            row = min(rows[0], self._model.rowCount() - 1)
            self.setCurrentIndex(self._model.index(row, col))

    # ---------------------------------------------------------------- 显隐

    def set_language_visible(self, lang: str, visible: bool) -> None:
        self._lang_visible[lang] = visible
        self._refresh_column_visibility()

    def set_extra_fields_visible(self, show: bool) -> None:
        self._show_extra = show
        self._refresh_column_visibility()

    def _refresh_column_visibility(self) -> None:
        for i, col in enumerate(self._model.columns):
            kind = col.key[0]
            if kind in ("lang", "temp", "charset"):
                lang = col.key[1]
                # 字体名/字符集是常驻工作列：仅随语言开关折叠，不受「全部字段」影响
                hidden = not self._lang_visible[lang]
                if kind == "lang":
                    nid = col.key[2]
                    if nid not in EDITABLE_NAME_IDS and not self._show_extra:
                        hidden = True
                self.setColumnHidden(i, hidden)

    # ---------------------------------------------------------------- 样式

    def _init_width(self) -> None:
        for i, col in enumerate(self._model.columns):
            if col.kind == "save":
                width = 68
            elif col.key[0] == "lang":
                width = 160
            else:
                width = _DEFAULT_WIDTHS.get(col.key[:2], 160)
            self.setColumnWidth(i, width)

    def _init_style(self) -> None:
        qss = (
            "QTableView { background: transparent; }\n"
            "QHeaderView::section { border: none; }\n"
        )
        setCustomStyleSheet(self, qss, qss)
