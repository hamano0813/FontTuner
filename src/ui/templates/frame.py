"""信息模板页：模板列表 + 新建/编辑/删除 + 一键应用到字体编辑页。

模板 = 各语言 name 字段（按语言 Tab 编辑）+ 共享横排四语言的
字重/字宽/斜体映射表（解析 {weight_sc}/{width_sc}/{italic_sc} 时按「模板」列查表取文本）。
映射表用 qfw TableView（去 HeaderCardWidget 包裹，改分区标题直接排版）。
"""

from copy import deepcopy

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
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
    TableView,
    ToolTipFilter,
    ToolTipPosition,
)
from qfluentwidgets.components.widgets.table_view import TableItemDelegate

from core.constants import WIDTH_LABELS, WIDTH_NAMES_EN, WEIGHT_TRANSLATIONS
from core.font_service import rename_placeholder_help
from core.models import LANG_LABELS, LANGS, NAME_ID_LABELS
from core.templates import TEMPLATE_NAME_IDS, VendorTemplate, load_templates, save_templates
from ui.editor.editors import CellLineEdit, CellSpinBox

_TEMPLATE_FIELDS = [(nid, NAME_ID_LABELS[nid]) for nid in TEMPLATE_NAME_IDS]

# 导航页签文本：翻译页 + 四语言字段页
_LANG_TAB_TEXTS = {"SC": "简体字段", "TC": "繁体字段", "JA": "日文字段", "EN": "英文字段"}

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
        self.enableTransparentBackground()  # 高度随页签容器（翻译页签更高）自适应，内部滚动


# ---------------------------------------------------------------- 映射表委托

class _MapItemDelegate(TableItemDelegate):
    """映射表委托基类：绘制前把视图默认委托的悬浮/按压/选中行状态同步过来。

    qfw 只把 hover/selected 状态写到默认 delegate 实例，按列挂的自定义
    delegate 收不到，需在 paint 前同步，否则该列悬浮/选中背景不显示。
    """

    def paint(self, painter, option, index):
        default = self.parent().delegate
        self.hoverRow = default.hoverRow
        self.pressedRow = default.pressedRow
        self.selectedRows = set(default.selectedRows)
        super().paint(painter, option, index)


class _MapValueDelegate(_MapItemDelegate):
    """值列委托：字重列用 CellSpinBox（左右箭头步进），字宽/斜体列只读。"""

    def __init__(self, parent, editable: bool):
        super().__init__(parent)
        self._editable = editable

    def createEditor(self, parent, option, index):
        if not self._editable:
            return None
        return CellSpinBox(parent, 1, 1000)

    def setEditorData(self, editor, index):
        editor.set_value(index.data(Qt.ItemDataRole.UserRole))
        alignment = index.data(Qt.ItemDataRole.TextAlignmentRole)
        if alignment is not None:
            editor.apply_alignment(alignment)

    def setModelData(self, editor, model, index):
        value = editor.get_value()
        model.setData(index, value, Qt.ItemDataRole.UserRole)
        model.setData(index, str(value), Qt.ItemDataRole.DisplayRole)


class _MapTextDelegate(_MapItemDelegate):
    """语言文本列委托：项目自带透明编辑器（无边框/无右键菜单/随主题变色）。"""

    def createEditor(self, parent, option, index):
        return CellLineEdit(parent)

    def setEditorData(self, editor, index):
        editor.set_value(index.data(Qt.ItemDataRole.DisplayRole))
        alignment = index.data(Qt.ItemDataRole.TextAlignmentRole)
        if alignment is not None:
            editor.apply_alignment(alignment)

    def setModelData(self, editor, model, index):
        text = editor.get_value()
        model.setData(index, text, Qt.ItemDataRole.DisplayRole)
        model.setData(index, text, Qt.ItemDataRole.EditRole)


# ---------------------------------------------------------------- 映射表

class _MapTableView(TableView):
    """映射表基类：列0=值，列1-4=简繁日英；qfw 行背景、紧凑行高、按内容定高。"""

    def __init__(self, value_editable: bool, parent=None):
        super().__init__(parent)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(28)
        self.setWordWrap(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setItemDelegateForColumn(0, _MapValueDelegate(self, value_editable))
        for c in range(1, 5):
            self.setItemDelegateForColumn(c, _MapTextDelegate(self))

    def _configure_columns(self) -> None:
        """列宽策略：五列等宽拉伸填满表宽。

        必须在 setModel 之后调用——QTableView.setModel 会重置表头
        各列为 Interactive，在此之前设置的 Stretch 会被清掉。
        """
        header = self.horizontalHeader()
        for c in range(5):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Stretch)

    def sizeHint(self) -> QSize:
        """按当前行数返回高度（QTableView 默认 256×192 不含行数，布局据此放置全部行）。"""
        model = getattr(self, "_model", None)
        if model is None:
            return super().sizeHint()
        h = (self.verticalHeader().defaultSectionSize() * max(1, model.rowCount())
             + self.horizontalHeader().height())
        return QSize(400, h)


class _MapTable(_MapTableView):
    """字重映射表（动态行）：列0=字重值可编辑 spinbox，加行/删行由对话框按钮驱动。"""

    def __init__(self, parent=None):
        super().__init__(True, parent)
        self._model = QStandardItemModel(0, 5, self)
        self._model.setHorizontalHeaderLabels(["字重值"] + [LANG_LABELS[l] for l in LANGS])
        self.setModel(self._model)
        self._configure_columns()

    def _insert_row(self, value, labels: dict[str, str]) -> None:
        r = self._model.rowCount()
        self._model.insertRow(r)
        value_item = QStandardItem(str(value))
        value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        value_item.setEditable(True)
        value_item.setData(value, Qt.ItemDataRole.UserRole)
        self._model.setItem(r, 0, value_item)
        for c, lang in enumerate(LANGS, start=1):
            item = QStandardItem(labels.get(lang, ""))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._model.setItem(r, c, item)

    def add_row(self, value, labels: dict[str, str] | None = None) -> None:
        self._insert_row(value, labels or {})
        self._resort()

    def remove_row_at(self, index: int) -> None:
        if 0 <= index < self._model.rowCount():
            self._model.removeRow(index)
            self._resort()

    def _resort(self) -> None:
        """添加/删除字重行后按字重值正序重排：已有 200,400，加 300 → 200,300,400。"""
        rows = []
        for r in range(self._model.rowCount()):
            value_item = self._model.item(r, 0)
            if value_item is None:
                continue
            value = value_item.data(Qt.ItemDataRole.UserRole)
            labels = {
                lang: (self._model.item(r, c).text() if self._model.item(r, c) else "")
                for c, lang in enumerate(LANGS, start=1)
            }
            rows.append((value, labels))
        rows.sort(key=lambda t: t[0])
        self._model.removeRows(0, self._model.rowCount())
        for value, labels in rows:
            self._insert_row(value, labels)

    def clear_rows(self) -> None:
        self._model.removeRows(0, self._model.rowCount())

    def rows(self) -> dict:
        """收集 {字重值: {语言: 文本}}，仅含至少一个非空文本的行。"""
        out: dict = {}
        for r in range(self._model.rowCount()):
            value_item = self._model.item(r, 0)
            if value_item is None:
                continue
            value = value_item.data(Qt.ItemDataRole.UserRole)
            labels: dict[str, str] = {}
            for c, lang in enumerate(LANGS, start=1):
                item = self._model.item(r, c)
                text = item.text().strip() if item else ""
                if text:
                    labels[lang] = text
            if labels:
                out[value] = labels
        return out

    def rowCount(self) -> int:
        return self._model.rowCount()

    def setCurrentCell(self, row: int, column: int) -> None:
        idx = self._model.index(row, column)
        if idx.isValid():
            self.setCurrentIndex(idx)

    def currentRow(self) -> int:
        return self.currentIndex().row()


class _WidthFlagTable(_MapTableView):
    """字宽 & FLAG 映射表（固定行）：9 档字宽 + 斜体一行。

    设计值列只读显示英文枚举（UltraCondensed…UltraExpanded / Italic）；
    语言列填各语言翻译。斜体只需 Italic 一行——非斜体无需翻译，
    将来可扩展 fsSelection 的其他位（Bold 等）。
    """

    def __init__(self, parent=None):
        super().__init__(False, parent)
        self._model = QStandardItemModel(0, 5, self)
        self._model.setHorizontalHeaderLabels(["设计值"] + [LANG_LABELS[l] for l in LANGS])
        self.setModel(self._model)
        self._configure_columns()

    # ---- 行操作（固定 9+1 行）----

    def _insert_row(self, display: str, key) -> None:
        r = self._model.rowCount()
        self._model.insertRow(r)
        value_item = QStandardItem(display)
        value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        value_item.setEditable(False)
        value_item.setData(key, Qt.ItemDataRole.UserRole)
        self._model.setItem(r, 0, value_item)
        for c in range(1, 5):
            item = QStandardItem("")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._model.setItem(r, c, item)

    def _fill_lang(self, r: int, labels: dict[str, str]) -> None:
        for c, lang in enumerate(LANGS, start=1):
            item = self._model.item(r, c)
            item.setText(labels.get(lang, ""))

    def clear_rows(self) -> None:
        self._model.removeRows(0, self._model.rowCount())

    def set_widths(self, width_map: dict, italic_map: dict, prefill_italic: bool = True) -> None:
        """装载：9 档字宽（SC 缺省填简体枚举）+ 斜体一行（新建模板时 SC 缺省「斜体」）。"""
        self.clear_rows()
        for v in sorted(WIDTH_LABELS):
            labels = dict(width_map.get(v, {}))
            labels.setdefault("SC", WIDTH_LABELS[v])
            self._insert_row(WIDTH_NAMES_EN.get(v, str(v)), ("width", v))
            self._fill_lang(self._model.rowCount() - 1, labels)
        labels = dict(italic_map.get(True, {}))
        if prefill_italic:
            labels.setdefault("SC", "斜体")
        self._insert_row("Italic", ("italic", True))
        self._fill_lang(self._model.rowCount() - 1, labels)

    def rows(self) -> tuple[dict[int, dict[str, str]], dict[bool, dict[str, str]]]:
        """收集 (width_map, italic_map)，仅含至少一个非空文本的行。"""
        width_map: dict[int, dict[str, str]] = {}
        italic_map: dict[bool, dict[str, str]] = {}
        for r in range(self._model.rowCount()):
            key_item = self._model.item(r, 0)
            if key_item is None:
                continue
            kind, value = key_item.data(Qt.ItemDataRole.UserRole)
            labels: dict[str, str] = {}
            for c, lang in enumerate(LANGS, start=1):
                item = self._model.item(r, c)
                text = item.text().strip() if item else ""
                if text:
                    labels[lang] = text
            if not labels:
                continue
            if kind == "width":
                width_map[value] = labels
            else:
                italic_map[value] = labels
        return width_map, italic_map


class TemplateDialog(MessageBoxBase):
    """新建/编辑模板表单：name 字段按语言 Tab + 共享横排四语言映射表（qfw TableView，去卡片化）。"""

    def __init__(self, parent=None, template: VendorTemplate | None = None):
        super().__init__(parent)
        self._template = template

        self.title_label = SubtitleLabel("新建模板" if template is None else "编辑模板", self)
        self.name_edit = LineEdit(self)
        self.name_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)  # 输入框禁用右键菜单

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

        # ---- 映射表（置于「翻译」页签，整宽排版：字宽&FLAG 在上、字重在下）----
        self.weight_table = _MapTable(self)
        self.weight_table.setMaximumHeight(150)  # 字重行多时内部滚动，不撑高页签
        self.btn_weight_add = PushButton(FIF.ADD, "加行", self)
        self.btn_weight_del = PushButton(FIF.DELETE, "删行", self)
        self.btn_weight_add.clicked.connect(self._add_weight_row)
        self.btn_weight_del.clicked.connect(self._del_weight_row)

        self.widthflag_table = _WidthFlagTable(self)

        translate_tab = QWidget(self)
        translate_tab.setObjectName("TranslateTab")
        t_layout = QVBoxLayout(translate_tab)
        t_layout.setSpacing(8)
        t_layout.setContentsMargins(0, 0, 0, 0)
        t_layout.addWidget(BodyLabel("字宽 & FLAG 映射表", self))
        t_layout.addWidget(self.widthflag_table)
        weight_head = QHBoxLayout()
        weight_head.addWidget(BodyLabel("字重映射表", self))
        weight_head.addStretch(1)
        weight_head.addWidget(self.btn_weight_add)
        weight_head.addWidget(self.btn_weight_del)
        t_layout.addLayout(weight_head)
        t_layout.addWidget(self.weight_table)

        # ---- 导航：文本翻译 | 简体字段 | 繁体字段 | 日文字段 | 英文字段 ----
        self.segmented = SegmentedWidget(self)
        self.stack = QStackedWidget(self)
        self.stack.addWidget(translate_tab)
        self.segmented.addItem(
            translate_tab.objectName(), "文本翻译",
            onClick=lambda checked=False: self.stack.setCurrentWidget(translate_tab),
        )
        self.lang_tabs: dict[str, _LangFieldTab] = {}
        for lang in LANGS:
            tab = _LangFieldTab(lang, self)
            self.lang_tabs[lang] = tab
            self.stack.addWidget(tab)
            self.segmented.addItem(
                tab.objectName(), _LANG_TAB_TEXTS[lang],
                onClick=lambda checked=False, w=tab: self.stack.setCurrentWidget(w),
            )

        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addLayout(meta_grid)
        self.viewLayout.addWidget(self.segmented)
        self.viewLayout.addWidget(self.stack)

        self.yesButton.setText("保存")
        self.cancelButton.setText("取消")

        self.widget.setMinimumSize(900, 760)
        self._load(template or VendorTemplate(name=""))

    def _add_weight_row(self):
        # 默认加行：字重 1、翻译全空（用户自己填；加行后自动按字重正序）
        self.weight_table.add_row(1, {})
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
        # 字重表（新建模板预填 100-900 九档 + 四语言默认翻译，旧模板按原数据装载）
        self.weight_table.clear_rows()
        if self._template is None:
            for value in sorted(WEIGHT_TRANSLATIONS):
                self.weight_table.add_row(value, dict(WEIGHT_TRANSLATIONS[value]))
        else:
            for value, labels in sorted(template.weight_map.items()):
                self.weight_table.add_row(value, labels)
        # 字宽 & FLAG 合并表（9 档字宽 + 斜体一行）
        self.widthflag_table.set_widths(
            template.width_map, template.italic_map,
            prefill_italic=self._template is None,
        )

    def result_template(self) -> VendorTemplate:
        field_values: dict[str, dict[int, str]] = {}
        for lang, tab in self.lang_tabs.items():
            values = {nid: edit.text().strip() for nid, edit in tab.edits.items() if edit.text().strip()}
            if values:
                field_values[lang] = values
        width_map, italic_map = self.widthflag_table.rows()
        return VendorTemplate(
            name=self.name_edit.text().strip() or "未命名模板",
            field_values=field_values,
            weight_map=self.weight_table.rows(),
            width_map=width_map,
            italic_map=italic_map,
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
