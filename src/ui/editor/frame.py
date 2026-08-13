"""字体编辑页：工具栏 + 字体表格 + 预览面板 + 保存集成。"""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QVBoxLayout
from qfluentwidgets import (
    Action,
    CommandBar,
    FluentIcon as FIF,
    InfoBar,
    InfoBarPosition,
    MessageBox,
    ProgressBar,
    RoundMenu,
    SwitchButton,
    ToggleButton,
    qconfig,
)
from qfluentwidgets.components.widgets.command_bar import CommandButton

from config import option
from core import fs, mapping
from core.font_service import rename_entries, resolve_rename_template, sort_entries
from core.models import LANG_PREFIX, LANGS
from core.templates import (
    apply_template,
    load_templates,
    resolve_entry_placeholders,
)
from ui.editor.columns import width_items
from ui.editor.delegates import (
    CheckBoxDelegate,
    ComboDelegate,
    ReadOnlyDelegate,
    SaveLangDelegate,
    SpinDelegate,
    TextDelegate,
)
from ui.editor.model import FontTreeModel
from ui.editor.preview import FontPreviewWidget
from ui.editor.table import FontTreeTableView
from ui.editor.worker import LoadWorker, SaveWorker
from ui.signals import app_signals


class EditorFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("EditorFrame")

        self.model = FontTreeModel(self)
        self.table = FontTreeTableView(self.model, self)
        self.preview = FontPreviewWidget(self)
        self._setup_delegates()

        self._worker = None  # 当前后台线程引用
        self._append_import = False  # 本次导入是否追加到现有表格（而非替换）

        self._build_toolbar()
        self._build_layout()

        self.table.selectionModel().currentChanged.connect(self._on_current_changed)
        self.model.valueChanged.connect(self._on_row_value_changed)
        self.table.deleteFromDiskRequested.connect(self._on_delete_from_disk)
        self.table.setCurrentIndex(self.model.index(0, 0))

    # ---------------------------------------------------------------- 界面

    def _build_toolbar(self):
        # ---- 第 1 行：三个功能按钮 → CommandBar ----
        self.cmd_bar = CommandBar(self)
        self.cmd_bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.cmd_bar.setSpaing(10)  # 按钮间距（qfw 方法名为 setSpaing）
        self.action_import = Action(FIF.FOLDER_ADD, "导入字体")
        self.action_import.triggered.connect(self._show_import_menu)
        self.action_template = Action(FIF.BRUSH, "应用模板")
        self.action_template.triggered.connect(self._show_template_menu)
        self.action_parse = Action(FIF.CODE, "解析")
        self.action_parse.triggered.connect(self._on_parse)
        self.action_save = Action(FIF.SAVE, "保存")
        self.action_save.triggered.connect(self._on_save)
        self.action_rename = Action(FIF.TAG, "重命名")
        self.action_rename.triggered.connect(self._on_rename)
        self.action_clear = Action(FIF.DELETE, "清空")
        self.action_clear.triggered.connect(self._on_clear)
        self.cmd_bar.addAction(self.action_import)
        self.cmd_bar.addAction(self.action_template)
        self.cmd_bar.addAction(self.action_parse)
        self.cmd_bar.addAction(self.action_save)
        self.cmd_bar.addAction(self.action_rename)
        self.cmd_bar.addAction(self.action_clear)
        # CommandBar 无内在宽度、默认 4px 间距，固定为内容宽度避免被网格拉伸后按钮挤在左边
        self.cmd_bar.resizeToSuitableWidth()
        # CommandBar 内部按钮（addAction 顺序与 _widgets 对应），供下拉菜单定位
        self.btn_import = self.cmd_bar._widgets[0]
        self.btn_template = self.cmd_bar._widgets[1]
        self.btn_parse = self.cmd_bar._widgets[2]
        self.btn_save = self.cmd_bar._widgets[3]
        self.btn_rename = self.cmd_bar._widgets[4]
        self.btn_clear = self.cmd_bar._widgets[5]

        # ---- 第 2 行：简繁日英 + 开关 ----
        self.lang_toggles: dict[str, ToggleButton] = {}
        for lang in LANGS:
            btn = ToggleButton(LANG_PREFIX[lang], self)
            btn.setChecked(True)
            btn.toggled.connect(lambda checked, l=lang: self.table.set_language_row_visible(l, checked))
            self.lang_toggles[lang] = btn

        self.switch_extra = SwitchButton("全部字段 关", self)
        self.switch_extra.setOnText("全部字段 开")
        self.switch_extra.setOffText("全部字段 关")
        self.switch_extra.checkedChanged.connect(self._on_switch_extra_changed)
        self.switch_preview = SwitchButton("字体预览 关", self)
        self.switch_preview.setOnText("字体预览 开")
        self.switch_preview.setOffText("字体预览 关")
        self.switch_preview.setChecked(True)
        self.switch_preview.checkedChanged.connect(self._on_switch_preview_changed)

        self.controls_row = QHBoxLayout()
        self.controls_row.setSpacing(8)  # 语言开关/字段开关之间留间距，避免挤在一起
        for lang in LANGS:
            self.controls_row.addWidget(self.lang_toggles[lang])
        self.controls_row.addSpacing(16)
        self.controls_row.addWidget(self.switch_extra)
        self.controls_row.addWidget(self.switch_preview)
        # 字体预览开关后：全部折叠 / 全部展开（折叠指示器已移出首列，靠这里整体控制）
        # 与第 1 行 CommandBar（导入/解析…）同款 CommandButton：图标 + 文字
        self.btn_collapse = self._make_command_button(FIF.UP, "全部折叠")
        self.btn_collapse.clicked.connect(self.table.collapse_all)
        self.btn_expand = self._make_command_button(FIF.DOWN, "全部展开")
        self.btn_expand.clicked.connect(self.table.expand_all)
        self.controls_row.addSpacing(8)
        self.controls_row.addWidget(self.btn_collapse)
        self.controls_row.addWidget(self.btn_expand)
        self.controls_row.addStretch(1)

    def _make_command_button(self, icon, text: str):
        """与第 1 行 CommandBar 同款的 CommandButton：图标 + 文字，不可勾选（瞬时动作）。"""
        btn = CommandButton(icon, self)
        btn.setText(text)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        return btn

    def _build_layout(self):
        # 表格占满剩余高度，预览固定在下部；与字体管理页一致：无分隔框，
        # 高度由页面布局自行管理（预览开关隐藏/显示预览区，表格自动补位）
        self.preview.setMinimumHeight(60)

        # 顶部单行：功能按钮（CommandBar）+ 语言/字段开关（预览文字已移入设置页，两行合并为一行）
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(16)
        top.addWidget(self.cmd_bar)
        top.addLayout(self.controls_row, 1)

        self.progress = ProgressBar(self)
        self.progress.setVisible(False)
        self.status_label = self._make_status_label()

        status_bar = QHBoxLayout()
        status_bar.addWidget(self.status_label, 1)
        status_bar.addWidget(self.progress, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.preview)
        layout.addLayout(status_bar)
        self.setLayout(layout)

    def _make_status_label(self):
        from qfluentwidgets import CaptionLabel
        label = CaptionLabel("尚未导入字体", self)
        return label

    def _on_switch_extra_changed(self, on: bool) -> None:
        self.table.set_extra_fields_visible(on)

    def _on_switch_preview_changed(self, on: bool) -> None:
        self.preview.setVisible(on)

    def _setup_delegates(self):
        for i, col in enumerate(self.model.columns):
            kind = col.kind
            if kind == "weight":
                # 字重 1-1000 数值直编（spinbox），不再用固定档位下拉
                self.table.setItemDelegateForColumn(i, SpinDelegate(self.table))
            elif kind == "width":
                # 字宽列纯下拉（禁止输入文字，只能从 9 个枚举选择）
                self.table.setItemDelegateForColumn(i, ComboDelegate(width_items(), self.table, editable=False))
            elif kind == "italic":
                self.table.setItemDelegateForColumn(i, CheckBoxDelegate(self.table))
            elif kind == "save":
                # 保存列：复选框 + 语言标签（简/繁/日/英）
                self.table.setItemDelegateForColumn(i, SaveLangDelegate(self.table))
            elif kind == "text":
                self.table.setItemDelegateForColumn(i, TextDelegate(self.table))
            else:
                self.table.setItemDelegateForColumn(i, ReadOnlyDelegate(self.table))

    # ---------------------------------------------------------------- 导入

    def import_paths(self, paths: list[str], append: bool = False):
        """导入字体或文件夹（供文件选择按钮等调用）。

        append=True 时新字体追加到表格现有内容之后（不清空），否则整体替换。
        """
        if not paths:
            return
        self._append_import = append
        self._start_worker(LoadWorker(list(paths), self), self._on_load_finished)

    def _show_import_menu(self):
        menu = RoundMenu("导入字体", self)
        files_action = Action(FIF.DOCUMENT, "选择字体文件…")
        files_action.triggered.connect(self._on_import_files)
        folder_action = Action(FIF.FOLDER, "选择文件夹…")
        folder_action.triggered.connect(self._on_import_folder)
        menu.addAction(files_action)
        menu.addAction(folder_action)
        menu.addSeparator()
        append_files_action = Action(FIF.DOCUMENT, "追加文件…")
        append_files_action.triggered.connect(self._on_append_files)
        append_folder_action = Action(FIF.FOLDER, "追加文件夹…")
        append_folder_action.triggered.connect(self._on_append_folder)
        menu.addAction(append_files_action)
        menu.addAction(append_folder_action)
        menu.exec(self.btn_import.mapToGlobal(self.btn_import.rect().bottomLeft()))

    def _pick_files(self) -> list[str]:
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择字体文件", option.import_dir.value,
            "字体文件 (*.ttf *.otf *.ttc *.otc)",
        )
        if files:
            qconfig.set(option.import_dir, os.path.dirname(files[0]))
        return files

    def _pick_folder(self) -> list[str]:
        folder = QFileDialog.getExistingDirectory(self, "选择字体文件夹", option.import_dir.value)
        if folder:
            qconfig.set(option.import_dir, folder)
            return [folder]
        return []

    def _on_import_files(self):
        files = self._pick_files()
        if files:
            self.import_paths(files)

    def _on_import_folder(self):
        paths = self._pick_folder()
        if paths:
            self.import_paths(paths)

    def _on_append_files(self):
        files = self._pick_files()
        if files:
            self.import_paths(files, append=True)

    def _on_append_folder(self):
        paths = self._pick_folder()
        if paths:
            self.import_paths(paths, append=True)

    def _on_load_finished(self, entries, errors):
        if self._append_import:
            current = self.model.get_entries()
            new_count = len(entries)
            entries = current + entries  # 追加到现有内容之后
            self.status_label.setText(f"已追加 {new_count} 个字体，共 {len(entries)} 个")
        else:
            self.status_label.setText(f"已加载 {len(entries)} 个字体")
        self._append_import = False
        sort_entries(entries)  # 统一按首选家族名→字重→字宽排序（含追加合并后的整体）
        self.model.set_entries(entries)
        if errors:
            InfoBar.error("部分文件加载失败", f"{len(errors)} 个文件加载失败：{errors[0][0]}",
                          parent=self.window(), position=InfoBarPosition.TOP, duration=3000)
        if entries:
            self.table.setCurrentIndex(self.model.index(0, 0))

    def _on_clear(self):
        """清空当前表格的全部字体（仅清空表格，不修改字体文件）。"""
        entries = self.model.get_entries()
        if not entries:
            InfoBar.info("表格已为空", "当前表格没有字体。", parent=self.window(),
                         position=InfoBarPosition.TOP, duration=3000)
            return
        if self._worker is not None:
            InfoBar.warning("正在加载中", "请等待当前导入完成后重试。", parent=self.window(),
                            position=InfoBarPosition.TOP, duration=3000)
            return
        box = MessageBox(
            "确认清空",
            f"将清空当前表格的全部 {len(entries)} 个字体（仅清空表格，不修改字体文件）。",
            self.window(),
        )
        box.yesButton.setText("清空")
        box.cancelButton.setText("取消")
        if not box.exec():
            return
        self.model.set_entries([])
        self.status_label.setText("已清空")

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

        self._start_worker(
            SaveWorker(entries, self, release_font=self.preview.release_font),
            self._on_save_finished,
        )

    def _on_save_finished(self, errors):
        if errors:
            InfoBar.error("保存完成（部分失败）", f"{len(errors)} 个文件保存失败：{errors[0][0]}",
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
            action = Action("（暂无模板，请在“信息模板”页创建）")
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
        self.model.set_entries(entries)  # 刷新表格显示（含新写入的占位符字段，留待「解析」展开）
        self.status_label.setText(f"已应用模板「{tmpl.name}」到 {len(targets)} 个字体")
        app_signals.project_edited.emit()

    def _selected_rows(self) -> list[int]:
        """选中的 index 去重为字体序号（父行或任一子行都命中其字体）。"""
        selection = self.table.selectionModel()
        return sorted({
            self.model.font_of(i)
            for i in selection.selectedIndexes()
            if i.isValid() and self.model.font_of(i) >= 0
        })

    def _on_parse(self):
        """把选中（无选中则全部）字体的 {} 占位符解析为正常文本，落进表格。

        同时解析「重命名模板」列（无占位符或解析不出的模板保持原样）。
        保存时 build_font_setting 会隐式做同样的事；此按钮让它提前可见，
        用户可直接看到最终文本再保存。
        """
        entries = self.model.get_entries()
        if not entries:
            InfoBar.warning("没有字体", "请先导入字体再解析。", parent=self.window(),
                            position=InfoBarPosition.TOP, duration=3000)
            return
        rows = self._selected_rows()
        targets = [entries[r] for r in rows] if rows else list(entries)
        total = 0
        for e in targets:
            total += resolve_entry_placeholders(e)
            total += int(resolve_rename_template(e))
        self.model.set_entries(entries)  # 刷新表格显示解析后的文本
        if total:
            self.status_label.setText(f"已解析 {total} 个字段中的占位符")
            app_signals.project_edited.emit()
        else:
            self.status_label.setText("没有可解析的占位符")

    def _on_rename(self):
        """按各字体的「重命名模板」列重命名载入字体的文件；模板为空则不重命名。

        重命名前先释放预览对字体的 QFontDatabase 注册（避免本进程占用锁）；
        其他程序占用导致的失败会逐个报告，不中断整批。
        """
        entries = self.model.get_entries()
        if not entries:
            InfoBar.warning("没有字体", "请先导入字体再重命名。", parent=self.window(),
                            position=InfoBarPosition.TOP, duration=3000)
            return
        renamed, skipped, errors = rename_entries(
            entries, release_font=self.preview.release_font,
        )
        self.model.set_entries(entries)  # 刷新表格显示新文件名
        parts = [f"重命名 {renamed} 个文件"]
        if skipped:
            parts.append(f"跳过 {skipped} 个文件")
        if errors:
            parts.append(f"失败 {len(errors)} 个文件")
        self.status_label.setText("，".join(parts))
        if errors:
            InfoBar.error("重命名完成（部分失败）", f"{len(errors)} 个文件重命名失败：{errors[0][0]}",
                          parent=self.window(), position=InfoBarPosition.TOP, duration=5000)
        elif renamed:
            InfoBar.success("重命名完成", f"已重命名 {renamed} 个文件。",
                            parent=self.window(), position=InfoBarPosition.TOP, duration=3000)
        if renamed or errors:
            app_signals.project_edited.emit()

    # ---------------------------------------------------------------- 从磁盘删除

    def _on_delete_from_disk(self, rows: list[int]) -> None:
        """把选中行的字体文件移入回收站（从磁盘删除，可恢复）。

        一个文件可能对应多行（TTC/OTC 多 face），按文件路径去重后统一删除；
        删除前先释放预览对该字体的 QFontDatabase 注册（解除本进程占用锁）。
        成功删除的路径对应行一并移出表格，失败（被占用等）的行保留并提示。
        """
        entries = self.model.get_entries()
        paths = sorted({entries[r].font_path for r in rows if 0 <= r < len(entries)})
        if not paths:
            return

        names = [os.path.basename(p) for p in paths]
        preview = "\n".join(f"· {n}" for n in names[:8]) + ("\n…" if len(names) > 8 else "")
        box = MessageBox("从磁盘删除",
                         f"将删除 {len(paths)} 个字体文件（优先移入回收站；"
                         f"无回收站的磁盘将永久删除）：\n{preview}\n\n"
                         "确定删除？",
                         self.window())
        box.yesButton.setText("删除")
        box.cancelButton.setText("取消")
        if not box.exec():
            return

        for p in paths:
            self.preview.release_font(p)  # 释放本进程对将被删除文件的注册占用
        recycled, permanent, failed = fs.delete_files(paths)

        deleted_paths = set(recycled) | set(permanent)
        if deleted_paths:
            # 只移除「文件确已删除」的字体；失败与无关字体都保留
            self.model.remove_fonts(
                [r for r in range(len(entries)) if entries[r].font_path in deleted_paths]
            )

        if failed:
            InfoBar.error("删除完成（部分失败）",
                          f"{len(failed)} 个文件删除失败（可能被占用）："
                          + "；".join(os.path.basename(p) for p in failed[:5]),
                          parent=self.window(), position=InfoBarPosition.TOP, duration=5000)
        elif permanent:
            InfoBar.warning("已删除（不可恢复）",
                            f"{len(permanent)} 个文件所在磁盘没有回收站，已永久删除："
                            + "；".join(os.path.basename(p) for p in permanent[:5]),
                            parent=self.window(), position=InfoBarPosition.TOP, duration=6000)
        elif recycled:
            InfoBar.success("已删除", f"已将 {len(recycled)} 个字体文件移入回收站。",
                            parent=self.window(), position=InfoBarPosition.TOP, duration=3000)

    # ---------------------------------------------------------------- 主题

    def reset_style(self):
        """主题切换后刷新表格自定义样式与下拉编辑器配色。"""
        self.table._init_style()
        self._setup_delegates()          # 重建委托（CellComboBox 构造时按 isDarkTheme 上色）
        self.table.viewport().update()   # 强制重绘（chip/文字颜色在绘制时取 isDarkTheme）
        self.preview.refresh_theme()     # 预览 label 文字颜色跟随主题

    # ---------------------------------------------------------------- 预览

    def _on_current_changed(self, current, previous):
        entries = self.model.get_entries()
        font_idx = self.model.font_of(current) if current.isValid() else -1
        if 0 <= font_idx < len(entries):
            self.preview.set_font(entries[font_idx])
        else:
            self.preview.set_font(None)

    def _on_row_value_changed(self, font_idx: int) -> None:
        """单元格编辑后刷新预览（字重/斜体/宽度变化需立即反映）。"""
        entries = self.model.get_entries()
        current = self.table.currentIndex()
        cur_font = self.model.font_of(current) if current.isValid() else -1
        if cur_font == font_idx and 0 <= font_idx < len(entries):
            self.preview.set_font(entries[font_idx])

    # ---------------------------------------------------------------- 后台线程

    def _start_worker(self, worker, on_finished):
        if self._worker is not None:
            return  # 已有处理在跑，忽略新请求（与 package/fontmgr 页一致）
        self._worker = worker
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # 不确定进度
        self.cmd_bar.setEnabled(False)  # 处理期间禁用三个功能按钮
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
        self.cmd_bar.setEnabled(True)
        self._worker = None

    # ---------------------------------------------------------------- 供外部

    def get_entries(self):
        return self.model.get_entries()
        self.model.set_entries(self.model.get_entries())
