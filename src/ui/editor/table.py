"""字体树形视图：qfw TreeView + 复制粘贴删除 + 语言子行显隐 + 额外字段列显隐。"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QContextMenuEvent, QKeyEvent, QKeySequence
from PySide6.QtWidgets import QAbstractItemView
from qfluentwidgets import Action, FluentIcon as FIF, RoundMenu, TreeView, setCustomStyleSheet
from qfluentwidgets.common.smooth_scroll import SmoothMode

from core.models import LANGS
from ui.editor.columns import is_default_visible

_DEFAULT_WIDTHS = {
    ("fixed", "templateName"): 100,
    ("fixed", "fontPath"): 220,
    ("fixed", "renameTemplate"): 220,
    ("fixed", "weight"): 80,
    ("fixed", "width"): 80,
    ("fixed", "italic"): 45,
    ("fixed", "numGlyphs"): 60,
}


class FontTreeTableView(TreeView):
    """树形表格：父节点=字体，4 子节点=简/繁/日/英。

    语言开关隐藏各父节点下对应语言子行；「全部字段」开关展开非常用 name 字段列。
    """

    deleteFromDiskRequested = Signal(list)  # 字体序号列表 → 页面处理从磁盘删除

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self._model = model
        self.setModel(model)

        self.setWordWrap(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ContiguousSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setAlternatingRowColors(False)
        self.setExpandsOnDoubleClick(False)  # 双击进入单元格编辑，不切换展开
        # 不绘制根节点折叠指示器（默认画在首列会压到「模板」单元格边缝上），
        # 折叠/展开改为：双击父节点第 1/2 列 + 工具栏「全部折叠/全部展开」按钮
        self.setRootIsDecorated(False)

        # 关闭 qfw 平滑滚动（高行数表格 60fps 插值重绘很卡），回退到原生滚动
        self.scrollDelagate.verticalSmoothScroll.setSmoothMode(SmoothMode.NO_SMOOTH)
        self.scrollDelagate.horizonSmoothScroll.setSmoothMode(SmoothMode.NO_SMOOTH)

        self.doubleClicked.connect(self._on_double_clicked)

        self._lang_visible = {lang: True for lang in LANGS}
        self._show_extra = False

        self._init_width()
        self._init_style()
        self._refresh_column_visibility()
        # 模型 reset（导入/移除字体）后重挂语言子行显隐并保持展开
        model.modelReset.connect(self._apply_lang_row_visibility)
        self.expandAll()

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
            self._model.paste_at(idx, idx.column())

    def _delete(self):
        indexes = self.selectionModel().selectedIndexes()
        if indexes:
            self._model.delete_selection(set(indexes))

    # ---------------------------------------------------------------- 右键菜单（按字体）

    def contextMenuEvent(self, e: QContextMenuEvent):
        menu = RoundMenu(parent=self)
        del_action = Action(FIF.DELETE, "删除选中字体")
        del_action.triggered.connect(self._remove_selected_rows)
        menu.addAction(del_action)
        menu.addSeparator()
        disk_action = Action(FIF.CANCEL, "从磁盘删除…")
        disk_action.triggered.connect(self._delete_from_disk)
        menu.addAction(disk_action)
        menu.exec(e.globalPos())
        e.accept()

    def _selected_fonts(self) -> list[int]:
        """选中的 index 去重为字体序号（父行或任一子行都命中其字体）。"""
        return sorted({
            self._model.font_of(i)
            for i in self.selectionModel().selectedIndexes()
            if i.isValid() and self._model.font_of(i) >= 0
        })

    def _delete_from_disk(self):
        fonts = self._selected_fonts()
        if fonts:
            self.deleteFromDiskRequested.emit(fonts)

    def _remove_selected_rows(self):
        """从界面移除选中的整字体（不删文件，仅不再编辑）。"""
        fonts = self._selected_fonts()
        if not fonts:
            return
        removed = self._model.remove_fonts(fonts)
        if removed and self._model.rowCount() > 0:
            col = self.currentIndex().column() if self.currentIndex().isValid() else 0
            row = min(fonts[0], self._model.rowCount() - 1)
            self.setCurrentIndex(self._model.index(row, col))

    # ---------------------------------------------------------------- 显隐

    def set_language_row_visible(self, lang: str, visible: bool) -> None:
        """顶部语言按钮：隐藏/显示每个父节点下对应语言子节点行。"""
        self._lang_visible[lang] = visible
        self._apply_lang_row_visibility()

    def set_extra_fields_visible(self, show: bool) -> None:
        self._show_extra = show
        self._refresh_column_visibility()

    def _apply_lang_row_visibility(self) -> None:
        for lang, visible in self._lang_visible.items():
            child = LANGS.index(lang)
            for f in range(self._model.rowCount()):
                parent = self._model.index(f, 0)
                self.setRowHidden(child, parent, not visible)
        self.expandAll()

    def _refresh_column_visibility(self) -> None:
        for i, col in enumerate(self._model.columns):
            self.setColumnHidden(i, not (self._show_extra or is_default_visible(col.key)))

    # ---------------------------------------------------------------- 折叠/展开

    def _on_double_clicked(self, index) -> None:
        """双击父节点第 1/2 列（模板/字体文件，均不可编辑）时切换该字体子节点折叠。"""
        if not index.isValid() or self._model.node_of(index) != 0:
            return
        if index.column() not in (0, 1):
            return
        # QTreeView 的 expand/isExpanded 按列敏感的 QModelIndex 存储，(0,0)≠(0,1)，
        # 统一归一到列 0 再判断/切换
        root = self._model.index(index.row(), 0, index.parent())
        if self.isExpanded(root):
            self.collapse(root)
        else:
            self.expand(root)

    def expand_all(self) -> None:
        for f in range(self._model.rowCount()):
            self.expand(self._model.index(f, 0))

    def collapse_all(self) -> None:
        for f in range(self._model.rowCount()):
            self.collapse(self._model.index(f, 0))

    # ---------------------------------------------------------------- 样式

    def _init_width(self) -> None:
        for i, col in enumerate(self._model.columns):
            key = col.key
            if col.kind == "save":
                width = 68
            elif key[0] == "temp":
                width = 140  # 字体名（临时名称）
            elif key[0] == "charset":
                width = 90  # 字符集值是短代码（GBK/Big5 等），列收窄
            elif key[0] == "lang":
                width = 100 if key[1] == 5 else 160  # 版本号(nameID 5)值较短，列收窄
            else:
                width = _DEFAULT_WIDTHS.get(key, 160)
            self.setColumnWidth(i, width)

    def _init_style(self) -> None:
        qss = (
            "QTreeView { background: transparent; }\n"
            "QHeaderView::section { border: none; }\n"
        )
        setCustomStyleSheet(self, qss, qss)
