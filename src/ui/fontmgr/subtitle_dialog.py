"""字幕字体适配对话框：表格列出字幕用到的字体名，下拉选择替换字体（可输入匹配）。

SearchableComboBox 参考 VAS（C:\\iCode\\VAS\\src\\ui\\table\\editor\\search_combo.py）：
可编辑 + NoInsert，下拉弹出期间把可打印字符/退格/删除路由回行编辑以持续输入，
回车取下拉高亮行确认。字面以外的过滤不依赖拼音——用每个字体的英文系统名作隐藏
匹配词（忽略大小写子串匹配）。
"""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHeaderView,
    QSizePolicy,
    QTableWidgetItem,
)
from qfluentwidgets import (
    BodyLabel,
    MessageBoxBase,
    ScrollBar,
    SubtitleLabel,
    TableWidget,
    isDarkTheme,
)


class SearchableComboBox(QComboBox):
    """可输入匹配下拉框（样式移植自 VAS search_combo）。

    外观：qfw ComboBox QSS 主题（透明底 + 圆角下拉 + qfw 滚动条），深/浅主题各自适配。
    选项以 (显示文本, 隐藏匹配词) 注入；输入实时过滤（显示文本或隐藏匹配词命中即
    保留，忽略大小写）。第一项固定为空（= 不替换）。
    """

    def __init__(self, items: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self._all_items: list[tuple[str, str]] = list(items)  # (text, keyword)
        self._highlighted_row: int = -1
        self._view_styled: bool = False

        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)  # 自由输入不插入为选项
        self.setCompleter(None)  # 禁用自动完成，避免补全干扰手动输入（VAS 同款）
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(28)
        self.setMaxVisibleItems(12)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFrame(False)

        # 深/浅主题 QSS：透明底 + 圆角下拉 + 项态（对齐 VAS search_combo）
        if isDarkTheme():
            self.setStyleSheet(
                "QComboBox { border: none; border-radius: 0px; background: transparent; "
                "color: white; outline: none; }"
                "QComboBox:hover { border: none; background: transparent; }"
                "QComboBox:focus { border: none; background: transparent; }"
                "QComboBox::drop-down { width: 32px; border: none; background: transparent; }"
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
                "QComboBox QListView { border-radius: 5px; }")
        else:
            self.setStyleSheet(
                "QComboBox { border: none; border-radius: 0px; background: transparent; "
                "color: black; outline: none; }"
                "QComboBox:hover { border: none; background: transparent; }"
                "QComboBox:focus { border: none; background: transparent; }"
                "QComboBox::drop-down { width: 32px; border: none; background: transparent; }"
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
                "QComboBox QListView { border-radius: 5px; }")

        le = self.lineEdit()
        le.setFrame(False)
        le.setClearButtonEnabled(True)
        le.setStyleSheet(
            "background: transparent; border: none; padding-left: 8px; color: white;"
            if isDarkTheme() else
            "background: transparent; border: none; padding-left: 8px; color: black;"
        )
        le.textEdited.connect(self._on_user_typed)
        # 下拉弹出后焦点在 QListView，把编辑键路由回行编辑（VAS 同款机制）
        self.view().installEventFilter(self)
        self.highlighted.connect(self._on_highlighted)
        self._rebuild("")

    # ---- 选项 ----

    def _filtered(self, query: str) -> list[str]:
        """按输入过滤：显示文本或英文系统名（隐藏匹配词）命中即保留，忽略大小写。"""
        q = query.strip().lower()
        if not q:
            return [text for text, _ in self._all_items]
        return [text for text, kw in self._all_items if q in text.lower() or q in kw.lower()]

    def _rebuild(self, query: str) -> None:
        keep = self.lineEdit().text()
        self.blockSignals(True)
        self.lineEdit().blockSignals(True)
        try:
            self.clear()
            self.addItems(self._filtered(query))
        finally:
            self.lineEdit().blockSignals(False)
            self.blockSignals(False)
        self.lineEdit().setText(keep)
        self.lineEdit().setCursorPosition(len(keep))
        if query and self.count() > 0:
            self.showPopup()  # 输入过滤后自动弹出，高亮首项由用户回车确认

    def set_selected(self, text: str) -> None:
        """预设选中项：仅在完全匹配时选中（否则保持空的第一项）。"""
        if not text:
            return
        try:
            idx = next(i for i, (t, _) in enumerate(self._all_items) if t == text)
        except StopIteration:
            return
        self.blockSignals(True)
        self.setCurrentIndex(idx)
        self.blockSignals(False)

    def current_text(self) -> str:
        """当前输入/选中的文本（空 = 不替换）。"""
        return self.lineEdit().text().strip()

    def showPopup(self) -> None:
        """弹出下拉时安装 qfw 滚动条（仅首次），样式与 VAS 一致。"""
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

    # ---- 输入/下拉 ----

    def _on_user_typed(self, text: str) -> None:
        self._rebuild(text)

    def _on_highlighted(self, index: int) -> None:
        if index >= 0:
            self._highlighted_row = index

    def wheelEvent(self, event) -> None:
        """禁止滚轮操作：既不切换选项，也不让事件冒泡到上层滚动列表。

        可编辑 combo 悬停滚轮容易误触，直接吞掉事件（下拉列表弹出后由视图自身滚动）。
        """
        event.accept()

    def eventFilter(self, obj, event) -> bool:
        """下拉弹出（焦点在 QListView）时将编辑键路由回行编辑，回车取高亮行确认。"""
        if (obj is self.view() and isinstance(event, QKeyEvent)
                and event.type() == QEvent.Type.KeyPress):
            le = self.lineEdit()
            if le is not None:
                key = event.key()
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if 0 <= self._highlighted_row < self.count():
                        text = self.itemText(self._highlighted_row)
                        le.setText(text)
                        le.setCursorPosition(len(text))
                    self.hidePopup()
                    return True
                if key == Qt.Key.Key_Backspace:
                    pos = le.cursorPosition()
                    if pos > 0:
                        cur = le.text()
                        new = cur[: pos - 1] + cur[pos:]
                        le.setText(new)
                        le.setCursorPosition(pos - 1)
                        self._on_user_typed(new)  # setText 只发 textChanged，需手动过滤
                    return True
                if key == Qt.Key.Key_Delete:
                    pos = le.cursorPosition()
                    cur = le.text()
                    if pos < len(cur):
                        new = cur[:pos] + cur[pos + 1:]
                        le.setText(new)
                        le.setCursorPosition(pos)
                        self._on_user_typed(new)
                    return True
                text = event.text()
                if (text and text.isprintable()
                        and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier)):
                    pos = le.cursorPosition()
                    cur = le.text()
                    new = cur[:pos] + text + cur[pos:]
                    le.setText(new)
                    le.setCursorPosition(pos + len(text))
                    self._on_user_typed(new)
                    return True
        return super().eventFilter(obj, event)


class SubtitleFontDialog(MessageBoxBase):
    """字幕字体适配：第 1 列只读显示字幕字体名，第 2 列下拉选择替换字体。

    完全匹配当前字体库的自动预选；未匹配的留空（= 不替换）。确定后经
    result_mapping() 取「旧字体名 -> 新字体名」映射（仅含非空替换）。
    """

    def __init__(self, subtitle_fonts: list[str], available_fonts: list[tuple[str, str]],
                 parent=None):
        super().__init__(parent)
        self.subtitle_fonts = list(subtitle_fonts)
        available = sorted(available_fonts)  # (win_name, en_name)，按显示名排序

        self.title_label = SubtitleLabel("字幕字体适配", self)
        matched = sum(1 for f in subtitle_fonts if f in {t for t, _ in available})
        self.hint = BodyLabel(
            f"字幕共用到 {len(subtitle_fonts)} 个字体名：与当前字体库完全匹配的已自动预选，"
            f"未匹配的默认留空（不替换）。可输入中文名或英文系统名过滤查找。", self)

        self.table = TableWidget(self)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["字幕中的字体名", "替换为（留空 = 不替换）"])
        self.table.setRowCount(len(subtitle_fonts))
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setWordWrap(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().resizeSection(0, 240)

        self._combos: list[SearchableComboBox] = []
        for row, name in enumerate(subtitle_fonts):
            cell = QTableWidgetItem(name)
            cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, cell)
            combo = SearchableComboBox([("", "")] + available, self.table)
            combo.set_selected(name)  # 完全匹配才预选，否则留空
            self._combos.append(combo)
            self.table.setCellWidget(row, 1, combo)

        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addWidget(self.hint)
        self.viewLayout.addWidget(self.table)
        self.widget.setMinimumSize(760, 480)
        self.yesButton.setText("替换")
        self.cancelButton.setText("取消")

    def result_mapping(self) -> dict[str, str]:
        """返回 旧字体名 -> 新字体名（仅含用户明确选择/输入的非空替换，排除同名）。"""
        mapping: dict[str, str] = {}
        for name, combo in zip(self.subtitle_fonts, self._combos):
            new = combo.current_text()
            if new and new != name:
                mapping[name] = new
        return mapping
