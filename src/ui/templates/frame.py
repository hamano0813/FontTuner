"""信息模板页：模板列表 + 新建/编辑/删除 + 一键应用到字体编辑页。

模板可同时覆盖多个语言：每个语言（简/繁/日/英）各自维护全部 name 字段。
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QListWidgetItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    FluentIcon as FIF,
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

from core.models import LANG_LABELS, LANGS, NAME_ID_LABELS
from core.templates import TEMPLATE_NAME_IDS, VendorTemplate, load_templates, save_templates

_TEMPLATE_FIELDS = [(nid, NAME_ID_LABELS[nid]) for nid in TEMPLATE_NAME_IDS]

# 占位符说明（tooltip 文案），安装到每个字段输入框
_PLACEHOLDER_HINT = (
    "字段支持 {weight} {width} {italic} {weight_num} {width_num} "
    "以及 {name_sc} {name_tc} {name_jp} {name_en}（临时名称）"
    "{charset_sc} {charset_tc} {charset_jp} {charset_en}（字符集）占位符，"
    "按字体动态生成。"
)


class _LangFieldTab(ScrollArea):
    """单个语言的字段编辑面板：字段多时限定高度内部滚动。"""

    def __init__(self, lang: str, parent=None):
        super().__init__(parent)
        self.setObjectName(f"LangTab{lang}")
        self.edits: dict[int, LineEdit] = {}

        content = QWidget(self)
        grid = QGridLayout(content)
        grid.setSpacing(12)
        for row, (nid, label) in enumerate(_TEMPLATE_FIELDS):
            grid.addWidget(BodyLabel(label, content), row, 0)
            edit = LineEdit(content)
            edit.setToolTip(_PLACEHOLDER_HINT)
            edit.installEventFilter(
                ToolTipFilter(edit, showDelay=300, position=ToolTipPosition.TOP)
            )
            self.edits[nid] = edit
            grid.addWidget(edit, row, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(len(_TEMPLATE_FIELDS), 1)  # 字段少时内容顶部对齐

        self.setWidget(content)
        self.setWidgetResizable(True)
        self.setMaximumHeight(380)  # 20 个字段也不让对话框过高，内部滚动
        self.enableTransparentBackground()  # 保持对话框底色，不显示滚动区自带背景


class TemplateDialog(MessageBoxBase):
    """新建/编辑模板表单：按语言分 Tab 编辑，可覆盖多个语言。"""

    def __init__(self, parent=None, template: VendorTemplate | None = None):
        super().__init__(parent)
        self._template = template

        self.title_label = SubtitleLabel("新建模板" if template is None else "编辑模板", self)
        self.name_edit = LineEdit(self)

        # 语言页签：简 / 繁 / 日 / 英
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

        name_row = QHBoxLayout()
        name_row.addWidget(BodyLabel("名称", self))
        name_row.addWidget(self.name_edit, 1)

        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addLayout(name_row)
        self.viewLayout.addSpacing(8)
        self.viewLayout.addWidget(self.segmented)
        self.viewLayout.addWidget(self.stack)

        self.yesButton.setText("保存")
        self.cancelButton.setText("取消")

        self.widget.setMinimumWidth(640)
        self._load(template or VendorTemplate(name=""))

    def _load(self, template: VendorTemplate) -> None:
        self.name_edit.setText(template.name)
        for lang, tab in self.lang_tabs.items():
            values = template.field_values.get(lang, {})
            for nid, edit in tab.edits.items():
                edit.setText(values.get(nid, ""))

    def result_template(self) -> VendorTemplate:
        field_values: dict[str, dict[int, str]] = {}
        for lang, tab in self.lang_tabs.items():
            values = {
                nid: edit.text().strip()
                for nid, edit in tab.edits.items()
                if edit.text().strip()
            }
            if values:
                field_values[lang] = values
        return VendorTemplate(
            name=self.name_edit.text().strip() or "未命名模板",
            field_values=field_values,
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
        self.btn_delete = PushButton(FIF.DELETE, "删除", self)
        self.btn_apply = PrimaryPushButton(FIF.BRUSH, "应用到字体编辑页", self)

        self.btn_new.clicked.connect(self._on_new)
        self.btn_edit.clicked.connect(lambda: self._on_edit())
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_apply.clicked.connect(self._on_apply)

        btn_bar = QHBoxLayout()
        btn_bar.addWidget(self.btn_new)
        btn_bar.addWidget(self.btn_edit)
        btn_bar.addWidget(self.btn_delete)
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
        has = self.list.currentRow() >= 0
        self.btn_edit.setEnabled(has)
        self.btn_delete.setEnabled(has)
        self.btn_apply.setEnabled(has)

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

    def _on_apply(self):
        tmpl = self._current()
        if tmpl is None:
            return
        editor = self.window().editor_frame
        editor.apply_template(tmpl, only_selected=True)

    def _persist(self):
        save_templates(self._templates)
        self._refresh()
