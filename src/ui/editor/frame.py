"""字体编辑页：工具栏 + 字体表格 + 预览面板 + 保存集成。"""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QSplitter, QVBoxLayout
from qfluentwidgets import (
    Action,
    FluentIcon as FIF,
    InfoBar,
    InfoBarPosition,
    MessageBox,
    ProgressBar,
    PushButton,
    RoundMenu,
    SwitchButton,
    ToggleButton,
    qconfig,
)

from config import option
from core import mapping
from core.models import LANG_PREFIX, LANGS
from core.templates import apply_template, load_templates, template_hints
from ui.editor.columns import ITALIC_ITEMS, weight_items, width_items
from ui.editor.delegates import CheckBoxDelegate, ComboDelegate, ReadOnlyDelegate, TextDelegate
from ui.editor.model import FontTableModel
from ui.editor.preview import FontPreviewWidget
from ui.editor.table import FontTableView
from ui.editor.worker import LoadWorker, SaveWorker
from ui.signals import app_signals


class EditorFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("EditorFrame")

        self.model = FontTableModel(self)
        self.table = FontTableView(self.model, self)
        self.preview = FontPreviewWidget(self)
        self._setup_delegates()

        self._worker = None  # 当前后台线程引用

        self._build_toolbar()
        self._build_layout()

        self.table.selectionModel().currentChanged.connect(self._on_current_changed)
        self.table.setCurrentIndex(self.model.index(0, 0))

    # ---------------------------------------------------------------- 界面

    def _build_toolbar(self):
        self.btn_import = PushButton(FIF.FOLDER_ADD, "导入字体", self)
        self.btn_save = PushButton(FIF.SAVE, "保存", self)
        self.btn_template = PushButton(FIF.BRUSH, "应用模板", self)

        self.lang_toggles: dict[str, ToggleButton] = {}
        for lang in LANGS:
            btn = ToggleButton(LANG_PREFIX[lang], self)
            btn.setChecked(True)
            btn.toggled.connect(lambda checked, l=lang: self.table.set_language_visible(l, checked))
            self.lang_toggles[lang] = btn

        self.switch_extra = SwitchButton("全部字段", self)
        self.switch_extra.checkedChanged.connect(self.table.set_extra_fields_visible)
        self.switch_preview = SwitchButton("预览", self)
        self.switch_preview.setChecked(True)
        self.switch_preview.checkedChanged.connect(lambda on: self.preview.setVisible(on))

        self.btn_import.clicked.connect(self._show_import_menu)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_template.clicked.connect(self._show_template_menu)

        self.toolbar = QHBoxLayout()
        for w in (self.btn_import, self.btn_save, self.btn_template):
            self.toolbar.addWidget(w)
        self.toolbar.addSpacing(24)
        for lang in LANGS:
            self.toolbar.addWidget(self.lang_toggles[lang])
        self.toolbar.addSpacing(16)
        self.toolbar.addWidget(self.switch_extra)
        self.toolbar.addWidget(self.switch_preview)
        self.toolbar.addStretch(1)

    def _build_layout(self):
        self.splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.splitter.addWidget(self.table)
        self.splitter.addWidget(self.preview)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setSizes([520, 160])

        self.progress = ProgressBar(self)
        self.progress.setVisible(False)
        self.status_label = self._make_status_label()

        status_bar = QHBoxLayout()
        status_bar.addWidget(self.status_label, 1)
        status_bar.addWidget(self.progress, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(self.toolbar)
        layout.addWidget(self.splitter, 1)
        layout.addLayout(status_bar)
        self.setLayout(layout)

    def _make_status_label(self):
        from qfluentwidgets import CaptionLabel
        label = CaptionLabel("尚未导入字体", self)
        return label

    def _setup_delegates(self):
        for i, col in enumerate(self.model.columns):
            kind = col.kind
            if kind == "weight":
                self.table.setItemDelegateForColumn(i, ComboDelegate(weight_items(), self.table))
            elif kind == "width":
                self.table.setItemDelegateForColumn(i, ComboDelegate(width_items(), self.table))
            elif kind == "italic":
                self.table.setItemDelegateForColumn(i, ComboDelegate(ITALIC_ITEMS, self.table))
            elif kind == "save":
                self.table.setItemDelegateForColumn(i, CheckBoxDelegate(self.table))
            elif kind == "text":
                self.table.setItemDelegateForColumn(i, TextDelegate(self.table))
            else:
                self.table.setItemDelegateForColumn(i, ReadOnlyDelegate(self.table))

    # ---------------------------------------------------------------- 导入

    def import_paths(self, paths: list[str]):
        """外部（拖拽/命令行）传入的字体或文件夹。"""
        if not paths:
            return
        self._start_worker(LoadWorker(list(paths), self), self._on_load_finished)

    def _show_import_menu(self):
        menu = RoundMenu("导入字体", self)
        files_action = Action(FIF.DOCUMENT, "选择字体文件…")
        files_action.triggered.connect(self._on_import_files)
        folder_action = Action(FIF.FOLDER, "选择文件夹…")
        folder_action.triggered.connect(self._on_import_folder)
        menu.addAction(files_action)
        menu.addAction(folder_action)
        menu.exec(self.btn_import.mapToGlobal(self.btn_import.rect().bottomLeft()))

    def _on_import_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择字体文件", option.import_dir.value,
            "字体文件 (*.ttf *.otf *.ttc *.otc)",
        )
        if files:
            qconfig.set(option.import_dir, os.path.dirname(files[0]))
            self.import_paths(files)

    def _on_import_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择字体文件夹", option.import_dir.value)
        if folder:
            qconfig.set(option.import_dir, folder)
            self.import_paths([folder])

    def _on_load_finished(self, entries, errors):
        self.model.set_entries(entries)
        self.status_label.setText(f"已加载 {len(entries)} 个字体")
        app_signals.fonts_loaded.emit()
        if errors:
            InfoBar.error("部分文件加载失败", f"{len(errors)} 个文件出错：{errors[0][0]}",
                          parent=self.window(), position=InfoBarPosition.TOP, duration=3000)
        if entries:
            self.table.setCurrentIndex(self.model.index(0, 0))

    # ---------------------------------------------------------------- 保存

    def _on_save(self):
        entries = self.model.get_entries()
        if not entries:
            InfoBar.warning("没有字体", "请先导入字体再保存。", parent=self.window(),
                            position=InfoBarPosition.TOP, duration=3000)
            return

        deletions: list[str] = []
        skipped: list[str] = []
        for e in entries:
            for lang in mapping.deleted_langs(e):
                deletions.append(f"{e.display_name()} · {LANG_PREFIX[lang]}")
            for lang in mapping.unsavable_langs(e):
                skipped.append(f"{e.display_name()} · {LANG_PREFIX[lang]}（未填家族名）")
        messages = []
        if deletions:
            preview = "\n".join(deletions[:8]) + ("\n…" if len(deletions) > 8 else "")
            messages.append(f"以下语言记录将被删除：\n{preview}")
        if skipped:
            preview = "\n".join(skipped[:8]) + ("\n…" if len(skipped) > 8 else "")
            messages.append(f"以下语言缺少家族名，本次不会写入：\n{preview}")
        if messages:
            box = MessageBox("确认保存", "\n\n".join(messages), self.window())
            box.yesButton.setText("继续保存")
            box.cancelButton.setText("取消")
            if not box.exec():
                return

        self._start_worker(SaveWorker(entries, self), self._on_save_finished)

    def _on_save_finished(self, errors):
        if errors:
            InfoBar.error("保存完成（有失败）", f"{len(errors)} 个文件失败：{errors[0][0]}",
                          parent=self.window(), position=InfoBarPosition.TOP, duration=5000)
        else:
            InfoBar.success("保存成功", "全部字体已写回。", parent=self.window(),
                            position=InfoBarPosition.TOP, duration=3000)
        app_signals.project_saved.emit()

    # ---------------------------------------------------------------- 模板

    def _show_template_menu(self):
        templates = load_templates()
        menu = RoundMenu("应用模板", self)
        for tmpl in templates:
            action = Action(FIF.BRUSH, tmpl.name)
            action.triggered.connect(lambda checked=False, t=tmpl: self._apply_template(t))
            menu.addAction(action)
        if not templates:
            action = Action("（暂无模板，请在“厂商模板”页创建）")
            action.setEnabled(False)
            menu.addAction(action)
        menu.exec(self.btn_template.mapToGlobal(self.btn_template.rect().bottomLeft()))

    def _apply_template(self, tmpl):
        """应用模板：有选中行则只应用到选中行，否则应用到全部。"""
        self.apply_template(tmpl)

    def apply_template(self, tmpl, only_selected: bool = True):
        entries = self.model.get_entries()
        if only_selected:
            rows = self._selected_rows()
            targets = [entries[r] for r in rows] if rows else list(entries)
        else:
            targets = list(entries)
        for e in targets:
            apply_template(e, tmpl)
        # 版本号作为输入提示（placeholder）显示在空单元格
        hints = {("lang", lang, nid): text for (lang, nid), text in template_hints(tmpl).items()}
        self.model.set_cell_hints(hints)
        self.model.set_entries(entries)
        self.status_label.setText(f"已应用模板「{tmpl.name}」到 {len(targets)} 个字体")
        app_signals.project_edited.emit()

    def _selected_rows(self) -> list[int]:
        selection = self.table.selectionModel()
        return sorted({i.row() for i in selection.selectedIndexes()})

    # ---------------------------------------------------------------- 预览

    def _on_current_changed(self, current, previous):
        entries = self.model.get_entries()
        if current.isValid() and 0 <= current.row() < len(entries):
            self.preview.set_font(entries[current.row()])
        else:
            self.preview.set_font(None)

    # ---------------------------------------------------------------- 后台线程

    def _start_worker(self, worker, on_finished):
        self._worker = worker
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # 不确定进度
        for w in (self.btn_import, self.btn_save, self.btn_template):
            w.setEnabled(False)
        worker.finished_ok.connect(on_finished)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_worker_finished)
        worker.start()

    def _on_progress(self, done, total):
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
            self.status_label.setText(f"处理中 {done}/{total}")

    def _on_worker_finished(self):
        self.progress.setVisible(False)
        for w in (self.btn_import, self.btn_save, self.btn_template):
            w.setEnabled(True)
        self._worker = None

    # ---------------------------------------------------------------- 供外部

    def get_entries(self):
        return self.model.get_entries()

    def refresh_after_translations(self):
        """字重/字宽翻译修改后：重建下拉委托并刷新表格显示。"""
        self._setup_delegates()
        self.model.set_entries(self.model.get_entries())
