"""信息模板页：模板列表 + 新建/编辑/删除 + 一键应用到字体编辑页。

模板 = 各语言 name 字段（按语言 Tab 编辑）+ 共享横排四语言的
字重/字宽/斜体映射表（解析 {weight_sc}/{width_sc}/{italic_sc} 时按「模板」列查表取文本）。
"""

from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QListWidgetItem,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    HeaderCardWidget,
    LineEdit,
    ListWidget,
    MessageBoxBase,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SegmentedWidget,
    SubtitleLabel,
    ToolTipFilter,
    ToolTipPosition,
)

from core.constants import WIDTH_LABELS
from core.font_service import rename_placeholder_help
from core.models import LANG_LABELS, LANGS, NAME_ID_LABELS
from core.templates import TEMPLATE_NAME_IDS, VendorTemplate, load_templates, save_templates

_TEMPLATE_FIELDS = [(nid, NAME_ID_LABELS[nid]) for nid in TEMPLATE_NAME_IDS]

# 占位符说明（tooltip 文案），安装到每个字段输入框
_PLACEHOLDER_HINT = (
    "字段支持 {weight} {width} {italic} {weight_num} {width_num} "
    "以及 {name_sc} {name_tc} {name_jp} {name_en}（临时名称）"
    "{charset_sc} {charset_tc} {charset_jp} {charset_en}（字符集）占位符，"
    "按字体动态生成；字重/字宽/斜体文本按本模板映射表 + 字体数值查表。"
)


class _LangFieldTab(ScrollArea):
    """单个语言的 name 字段编辑面板（字重/字宽/斜体映射在对话框下方共享区域）。"""

    def __init__(self, lang: str, parent=None):
        super().__init__(parent)
        self.setObjectName(f"LangTab{lang}")
        self.edits: dict[int, LineEdit] = {}

        content = QWidget(self)
        outer = QVBoxLayout(content)
        outer.setSpacing(12)

        grid = QGridLayout()
        grid.setSpacing(12)
        for row, (nid, label) in enumerate(_TEMPLATE_FIELDS):
            grid.addWidget(BodyLabel(label, content), row, 0)
            edit = LineEdit(content)
            edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)  # 输入框禁用右键菜单
            edit.setToolTip(_PLACEHOLDER_HINT)
            edit.installEventFilter(
                ToolTipFilter(edit, showDelay=300, position=ToolTipPosition.TOP)
            )
            self.edits[nid] = edit
            grid.addWidget(edit, row, 1)
        grid.setColumnStretch(1, 1)
        outer.addLayout(grid)
        outer.addStretch(1)

        self.setWidget(content)
        self.setWidgetResizable(True)
        self.setMaximumHeight(320)  # 内容多时也不让对话框过高，内部滚动
        self.enableTransparentBackground()


class _MapTable(QTableWidget):
    """横排四语言映射表：列0=值（字重用可编辑 spinbox、字宽/斜体用固定文本），列1-4=简繁日英。

    value_editable=True：字重动态行，带加行/删行；
    value_editable=False：字宽/斜体固定行。
    """

    def __init__(self, value_editable: bool, value_text=None, parent=None):
        super().__init__(parent)
        self._value_editable = value_editable
        self._values: list[object] = []  # 每行真实值（字重 int / 字宽 int / 斜体 bool）
        self._value_text = value_text or (lambda v: str(v))
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(
            ["字重值" if value_editable else "设计值"] + [LANG_LABELS[l] for l in LANGS]
        )
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for c in range(1, 5):
            self.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeMode.Stretch)

    def add_row(self, value, labels: dict[str, str] | None = None) -> None:
        labels = labels or {}
        r = self.rowCount()
        self.insertRow(r)
        self._values.append(value)
        if self._value_editable:
            spin = QSpinBox(self)
            spin.setRange(1, 1000)
            spin.setValue(int(value))
            spin.setFrame(False)
            spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setCellWidget(r, 0, spin)
        else:
            item = QTableWidgetItem(self._value_text(value))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.setItem(r, 0, item)
        for c, lang in enumerate(LANGS, start=1):
            edit = LineEdit(self)
            edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)  # 输入框禁用右键菜单
            edit.setText(labels.get(lang, ""))
            self.setCellWidget(r, c, edit)

    def remove_row_at(self, index: int) -> None:
        if 0 <= index < self.rowCount():
            self.removeRow(index)
            self._values.pop(index)

    def clear_rows(self) -> None:
        while self.rowCount():
            self.removeRow(0)
        self._values.clear()

    def rows(self) -> dict:
        """收集 {真实值: {语言: 文本}}，仅含至少一个非空文本的行。"""
        out: dict = {}
        for r in range(self.rowCount()):
            value = self._values[r]
            if self._value_editable:
                spin = self.cellWidget(r, 0)
                if spin is not None:
                    value = spin.value()
            labels: dict[str, str] = {}
            for c, lang in enumerate(LANGS, start=1):
                edit = self.cellWidget(r, c)
                text = edit.text().strip() if edit else ""
                if text:
                    labels[lang] = text
            if labels:
                out[value] = labels
        return out


_WIDTH_VALUE_TEXT = lambda v: f"{v} · {WIDTH_LABELS.get(v, str(v))}"


class TemplateDialog(MessageBoxBase):
    """新建/编辑模板表单：name 字段按语言 Tab + 共享横排四语言的字重/字宽/斜体映射表。"""

    def __init__(self, parent=None, template: VendorTemplate | None = None):
        super().__init__(parent)
        self._template = template

        self.title_label = SubtitleLabel("新建模板" if template is None else "编辑模板", self)
        self.name_edit = LineEdit(self)
        self.name_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)  # 输入框禁用右键菜单

        # ---- 语言页签：name 字段 ----
        self.segmented = SegmentedWidget(self)
        self.stack = QStackedWidget(self)
        self.lang_tabs: dict[str, _LangFieldTab] = {}
        for lang in LANGS:
            tab = _LangFieldTab(lang, self)
            self.lang_tabs[lang] = tab
            self.stack.addWidget(tab)
            self.segmented.addItem(
                tab.objectName(), LANG_LABELS[lang],
                onClick=lambda checked=False, w=tab: self.stack.setCurrentWidget(w),
            )

        # ---- 名称 / 重命名模板 ----
        meta_grid = QGridLayout()
        meta_grid.setSpacing(8)
        meta_grid.addWidget(BodyLabel("名称", self), 0, 0)
        meta_grid.addWidget(self.name_edit, 0, 1)
        meta_grid.addWidget(BodyLabel("重命名模板", self), 1, 0)
        self.rename_edit = LineEdit(self)
        self.rename_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)  # 输入框禁用右键菜单
        self.rename_edit.setClearButtonEnabled(True)
        self.rename_edit.setPlaceholderText(
            "空 = 应用模板时不重命名；如 {preferred_family_sc} {weight_sc} {width_sc} {version_sc}"
        )
        self.rename_edit.setToolTip(rename_placeholder_help())
        self.rename_edit.installEventFilter(
            ToolTipFilter(self.rename_edit, showDelay=300, position=ToolTipPosition.TOP)
        )
        meta_grid.addWidget(self.rename_edit, 1, 1)
        meta_grid.setColumnStretch(1, 1)

        # ---- 共享横排四语言映射表 ----
        self.weight_table = _MapTable(True, parent=self)
        self.weight_table.setMaximumHeight(150)
        self.btn_weight_add = PushButton(FIF.ADD, "加行", self)
        self.btn_weight_del = PushButton(FIF.DELETE, "删行", self)
        self.btn_weight_add.clicked.connect(self._add_weight_row)
        self.btn_weight_del.clicked.connect(self._del_weight_row)

        self.width_table = _MapTable(False, _WIDTH_VALUE_TEXT, self)
        self.width_table.setMaximumHeight(250)
        self.italic_table = _MapTable(False, parent=self)
        self.italic_table.setMaximumHeight(110)

        weight_card = HeaderCardWidget("字重映射表", self)
        wbar = QHBoxLayout()
        wbar.addWidget(self.btn_weight_add)
        wbar.addWidget(self.btn_weight_del)
        wbar.addStretch(1)
        weight_card.viewLayout.addLayout(wbar)
        weight_card.viewLayout.addWidget(self.weight_table)

        width_card = HeaderCardWidget("字宽映射表（9 档固定）", self)
        width_card.viewLayout.addWidget(self.width_table)

        italic_card = HeaderCardWidget("斜体映射表（2 档固定）", self)
        italic_card.viewLayout.addWidget(self.italic_table)

        map_grid = QGridLayout()
        map_grid.setSpacing(12)
        map_grid.addWidget(weight_card, 0, 0, 1, 2)
        map_grid.addWidget(width_card, 1, 0)
        map_grid.addWidget(italic_card, 1, 1)
        map_grid.setColumnStretch(0, 1)
        map_grid.setColumnStretch(1, 1)

        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addLayout(meta_grid)
        self.viewLayout.addSpacing(8)
        self.viewLayout.addWidget(self.segmented)
        self.viewLayout.addWidget(self.stack)
        self.viewLayout.addSpacing(8)
        self.viewLayout.addWidget(BodyLabel("字重 / 字宽 / 斜体映射表（四语言横排）", self))
        self.viewLayout.addLayout(map_grid)

        self.yesButton.setText("保存")
        self.cancelButton.setText("取消")

        self.widget.setMinimumSize(900, 780)
        self._load(template or VendorTemplate(name=""))

    def _add_weight_row(self):
        self.weight_table.add_row(400, {"SC": "常规", "EN": "Regular"})
        self.weight_table.setCurrentCell(self.weight_table.rowCount() - 1, 0)

    def _del_weight_row(self):
        r = self.weight_table.currentRow()
        if r >= 0:
            self.weight_table.remove_row_at(r)

    def _load(self, template: VendorTemplate) -> None:
        self.name_edit.setText(template.name)
        self.rename_edit.setText(template.rename_template or "")
        for lang, tab in self.lang_tabs.items():
            values = template.field_values.get(lang, {})
            for nid, edit in tab.edits.items():
                edit.setText(values.get(nid, ""))
        # 字重表
        self.weight_table.clear_rows()
        for value, labels in sorted(template.weight_map.items()):
            self.weight_table.add_row(value, labels)
        # 字宽表（9 行固定；SC 缺省预填写死枚举，其余语言按模板值）
        self.width_table.clear_rows()
        for v in sorted(WIDTH_LABELS):
            labels = dict(template.width_map.get(v, {}))
            labels.setdefault("SC", WIDTH_LABELS[v])
            self.width_table.add_row(v, labels)
        # 斜体表（2 行固定）
        self.italic_table.clear_rows()
        for flag in (False, True):
            self.italic_table.add_row(flag, template.italic_map.get(flag, {}))

    def result_template(self) -> VendorTemplate:
        field_values: dict[str, dict[int, str]] = {}
        for lang, tab in self.lang_tabs.items():
            values = {nid: edit.text().strip() for nid, edit in tab.edits.items() if edit.text().strip()}
            if values:
                field_values[lang] = values
        return VendorTemplate(
            name=self.name_edit.text().strip() or "未命名模板",
            field_values=field_values,
            weight_map=self.weight_table.rows(),
            width_map=self.width_table.rows(),
            italic_map=self.italic_table.rows(),
            rename_template=self.rename_edit.text().strip(),
        )


class TemplateFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("TemplateFrame")
        self._templates: list[VendorTemplate] = load_templates()

        self.title = SubtitleLabel("信息模板", self)
        self.hint = BodyLabel("维护字体信息字段集，在「字体编辑」页一键应用到选中/全部字体。", self)

        self.list = ListWidget(self)
        self.list.itemSelectionChanged.connect(self._update_buttons)
        self.list.itemDoubleClicked.connect(self._on_item_double_clicked)

        self.btn_new = PushButton(FIF.ADD, "新建", self)
        self.btn_edit = PushButton(FIF.EDIT, "编辑", self)
        self.btn_copy = PushButton(FIF.COPY, "复制", self)
        self.btn_delete = PushButton(FIF.DELETE, "删除", self)
        self.btn_up = PushButton(FIF.UP, "上移", self)
        self.btn_down = PushButton(FIF.DOWN, "下移", self)
        self.btn_apply = PrimaryPushButton(FIF.BRUSH, "应用到字体编辑页", self)

        self.btn_new.clicked.connect(self._on_new)
        self.btn_edit.clicked.connect(lambda: self._on_edit())
        self.btn_copy.clicked.connect(self._on_copy)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_up.clicked.connect(self._on_move_up)
        self.btn_down.clicked.connect(self._on_move_down)
        self.btn_apply.clicked.connect(self._on_apply)

        btn_bar = QHBoxLayout()
        btn_bar.addWidget(self.btn_new)
        btn_bar.addWidget(self.btn_edit)
        btn_bar.addWidget(self.btn_copy)
        btn_bar.addWidget(self.btn_delete)
        btn_bar.addSpacing(8)
        btn_bar.addWidget(self.btn_up)
        btn_bar.addWidget(self.btn_down)
        btn_bar.addStretch(1)
        btn_bar.addWidget(self.btn_apply)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.hint)
        layout.addWidget(self.list, 1)
        layout.addLayout(btn_bar)
        self.setLayout(layout)

        self._refresh()
        self._update_buttons()

    def _refresh(self) -> None:
        self.list.clear()
        for tmpl in self._templates:
            item = QListWidgetItem(tmpl.name)
            item.setData(Qt.ItemDataRole.UserRole, tmpl)
            self.list.addItem(item)

    def _update_buttons(self) -> None:
        row = self.list.currentRow()
        has = row >= 0
        self.btn_edit.setEnabled(has)
        self.btn_copy.setEnabled(has)
        self.btn_delete.setEnabled(has)
        self.btn_apply.setEnabled(has)
        self.btn_up.setEnabled(has and row > 0)
        self.btn_down.setEnabled(has and row < self.list.count() - 1)

    def _current(self) -> VendorTemplate | None:
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_new(self):
        dlg = TemplateDialog(self.window())
        if dlg.exec():
            self._templates.append(dlg.result_template())
            self._persist()

    def _on_item_double_clicked(self, item):
        """双击列表项直接弹出编辑框。"""
        tmpl = item.data(Qt.ItemDataRole.UserRole) if item else None
        if tmpl is not None:
            self._on_edit(tmpl)

    def _on_edit(self, tmpl: VendorTemplate | None = None):
        tmpl = tmpl if tmpl is not None else self._current()
        if tmpl is None:
            return
        dlg = TemplateDialog(self.window(), tmpl)
        if dlg.exec():
            index = self._templates.index(tmpl)
            self._templates[index] = dlg.result_template()
            self._persist()

    def _on_delete(self):
        tmpl = self._current()
        if tmpl is None:
            return
        self._templates.remove(tmpl)
        self._persist()

    def _on_copy(self):
        """复制当前模板为同名加「 副本」后缀的新模板，追加到列表末尾。"""
        tmpl = self._current()
        if tmpl is None:
            return
        tmpl_copy = deepcopy(tmpl)
        tmpl_copy.name = f"{tmpl.name} 副本"
        self._templates.append(tmpl_copy)
        self._persist()
        self.list.setCurrentRow(len(self._templates) - 1)

    def _on_move_up(self):
        """上移：与前一模板交换位置，保持选中跟随移动。"""
        row = self.list.currentRow()
        if row <= 0:
            return
        self._templates[row], self._templates[row - 1] = \
            self._templates[row - 1], self._templates[row]
        self._persist()
        self.list.setCurrentRow(row - 1)

    def _on_move_down(self):
        """下移：与后一模板交换位置，保持选中跟随移动。"""
        row = self.list.currentRow()
        if row < 0 or row >= len(self._templates) - 1:
            return
        self._templates[row], self._templates[row + 1] = \
            self._templates[row + 1], self._templates[row]
        self._persist()
        self.list.setCurrentRow(row + 1)

    def _on_apply(self):
        tmpl = self._current()
        if tmpl is None:
            return
        editor = self.window().editor_frame
        editor.apply_template(tmpl, only_selected=True)

    def _persist(self):
        save_templates(self._templates)
        self._refresh()
