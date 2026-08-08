"""厂商模板页：模板列表 + 新建/编辑/删除 + 一键应用到字体编辑页。

模板可同时覆盖多个语言：每个语言（简/繁/日/英）各自维护
版权/许可/厂商/首选家族名/版本号 字段，另有全局的字重/字宽/斜体。
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QVBoxLayout,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    LineEdit,
    MessageBoxBase,
    PrimaryPushButton,
    PushButton,
    SegmentedWidget,
    SubtitleLabel,
    isDarkTheme,
)

from core.models import LANG_LABELS, LANGS
from core.templates import TEMPLATE_NAME_IDS, VendorTemplate, load_templates, save_templates

_TEMPLATE_FIELDS = [
    (0, "版权"),
    (13, "许可"),
    (8, "厂商"),
    (16, "首选家族名"),
    (5, "版本号（输入提示）"),
]


class _LangFieldTab(QFrame):
    """单个语言的字段编辑面板。"""

    def __init__(self, lang: str, parent=None):
        super().__init__(parent)
        self.setObjectName(f"LangTab{lang}")
        self.edits: dict[int, LineEdit] = {}
        grid = QGridLayout(self)
        grid.setSpacing(12)
        for row, (nid, label) in enumerate(_TEMPLATE_FIELDS):
            grid.addWidget(BodyLabel(label, self), row, 0)
            edit = LineEdit(self)
            self.edits[nid] = edit
            grid.addWidget(edit, row, 1)
        grid.setColumnStretch(1, 1)


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
        self.format_hint = CaptionLabel(
            "提示：家族名支持 {weight} {width} {italic} {weight_num} {width_num} 占位符，按字体动态生成；"
            "版本号只作为输入提示，不写入数据。", self,
        )
        self.viewLayout.addWidget(self.format_hint)

        self.yesButton.setText("保存")
        self.cancelButton.setText("取消")

        self.widget.setMinimumWidth(520)
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

        self.title = SubtitleLabel("厂商模板", self)
        self.hint = BodyLabel("维护厂商字段集，在「字体编辑」页一键应用到选中/全部字体。", self)

        self.list = QListWidget(self)
        self.list.itemSelectionChanged.connect(self._update_buttons)

        self.btn_new = PushButton(FIF.ADD, "新建", self)
        self.btn_edit = PushButton(FIF.EDIT, "编辑", self)
        self.btn_delete = PushButton(FIF.DELETE, "删除", self)
        self.btn_apply = PrimaryPushButton(FIF.BRUSH, "应用到字体编辑页", self)

        self.btn_new.clicked.connect(self._on_new)
        self.btn_edit.clicked.connect(self._on_edit)
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
        self._apply_theme()

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

    def _on_edit(self):
        tmpl = self._current()
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

    def _apply_theme(self):
        color = "#1e1e1e" if isDarkTheme() else "#f0f0f0"
        text = "#ffffff" if isDarkTheme() else "#1a1a1a"
        self.list.setStyleSheet(
            f"QListWidget {{ background: {color}; border-radius: 8px; border: none; "
            f"color: {text}; padding: 4px; }}"
            "QListWidget::item { height: 36px; padding-left: 10px; border-radius: 5px; }"
            "QListWidget::item:selected { background: rgba(0, 120, 212, 0.7); }"
        )
