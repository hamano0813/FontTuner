"""信息模板页：模板列表 + 新建/编辑/删除 + 一键应用到字体编辑页。

新建/编辑对话框（TemplateDialog）在 ui/templates/dialog.py。
"""

from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QListWidgetItem, QVBoxLayout
from qfluentwidgets import (
    BodyLabel,
    FluentIcon as FIF,
    ListWidget,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
)

from core.templates import VendorTemplate, load_templates, save_templates
from ui.templates.dialog import TemplateDialog


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
