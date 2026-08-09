"""解包/打包页：TTC/OTC 集合解包为独立 TTF/OTF；多个 TTF/OTF 打包为集合。

解包支持勾选子字体；输出用字体内名称命名（家族名-字重）。
打包格式可选 自动/ttc/otc。后台线程 + 进度条，复刻字体编辑页 worker 模式。
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QListWidgetItem,
    QStackedWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    FluentIcon as FIF,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    ListWidget,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    SegmentedWidget,
    SubtitleLabel,
    TreeWidget,
    qconfig,
)

from config import option
from core import package
from ui.package.worker import PackWorker, UnpackWorker


class PackageFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("PackageFrame")
        self._worker = None

        self.title = SubtitleLabel("解包 / 打包", self)
        self.hint = CaptionLabel(
            "TTC/OTC 集合解包为独立 TTF/OTF；多个 TTF/OTF 打包为集合文件。", self)

        self.segmented = SegmentedWidget(self)
        self.stack = QStackedWidget(self)
        self.unpack_panel = self._build_unpack_panel()
        self.pack_panel = self._build_pack_panel()
        self.stack.addWidget(self.unpack_panel)
        self.stack.addWidget(self.pack_panel)
        self.segmented.addItem(
            self.unpack_panel.objectName(), "解包",
            onClick=lambda checked=False, w=self.unpack_panel: self.stack.setCurrentWidget(w),
        )
        self.segmented.addItem(
            self.pack_panel.objectName(), "打包",
            onClick=lambda checked=False, w=self.pack_panel: self.stack.setCurrentWidget(w),
        )

        self.progress = ProgressBar(self)
        self.progress.setVisible(False)
        self.status_label = CaptionLabel("", self)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.hint)
        layout.addSpacing(8)
        layout.addWidget(self.segmented)
        layout.addWidget(self.stack, 1)
        layout.addSpacing(6)
        layout.addWidget(self.progress)
        layout.addWidget(self.status_label)
        self.setLayout(layout)

        self.unpack_out_dir.setText(option.package_out_dir.value)
        self.pack_out_dir.setText(option.package_out_dir.value)

    # ---------------------------------------------------------------- 解包面板

    def _build_unpack_panel(self) -> QWidget:
        panel = QWidget(self)
        panel.setObjectName("UnpackPanel")
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 8, 0, 0)

        top = QHBoxLayout()
        self.unpack_add = PushButton(FIF.FOLDER_ADD, "添加集合文件", panel)
        self.unpack_add.clicked.connect(self._on_unpack_add)
        self.unpack_check_all = PushButton("全选", panel)
        self.unpack_check_all.clicked.connect(lambda: self._set_all_checked(True))
        self.unpack_check_none = PushButton("全不选", panel)
        self.unpack_check_none.clicked.connect(lambda: self._set_all_checked(False))
        self.unpack_remove = PushButton(FIF.DELETE, "移除选中", panel)
        self.unpack_remove.clicked.connect(self._on_unpack_remove)
        top.addWidget(self.unpack_add)
        top.addWidget(self.unpack_check_all)
        top.addWidget(self.unpack_check_none)
        top.addWidget(self.unpack_remove)
        top.addStretch(1)
        v.addLayout(top)

        self.unpack_tree = TreeWidget(panel)
        self.unpack_tree.setColumnCount(1)
        self.unpack_tree.setHeaderLabels(["集合文件 → 子字体"])
        self.unpack_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        v.addWidget(self.unpack_tree, 1)

        dir_row = QHBoxLayout()
        dir_row.addWidget(BodyLabel("输出目录", panel))
        self.unpack_out_dir = LineEdit(panel)
        self.unpack_out_dir.setReadOnly(True)
        browse = PushButton("浏览…", panel)
        browse.clicked.connect(lambda: self._pick_out_dir(self.unpack_out_dir))
        dir_row.addWidget(self.unpack_out_dir, 1)
        dir_row.addWidget(browse)
        v.addLayout(dir_row)

        name_hint = CaptionLabel("输出以字体内部名称（家族名-字重）命名，重名时自动追加序号。", panel)
        v.addWidget(name_hint)

        run_row = QHBoxLayout()
        run_row.addStretch(1)
        self.unpack_run = PrimaryPushButton(FIF.PLAY, "开始解包", panel)
        self.unpack_run.clicked.connect(self._run_unpack)
        run_row.addWidget(self.unpack_run)
        v.addLayout(run_row)
        return panel

    def _on_unpack_add(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择集合文件", option.import_dir.value, "集合文件 (*.ttc *.otc)")
        if not files:
            return
        qconfig.set(option.import_dir, os.path.dirname(files[0]))
        for path in files:
            self._add_collection(path)

    def _add_collection(self, path: str) -> None:
        root = QTreeWidgetItem([os.path.basename(path)])
        root.setData(0, Qt.ItemDataRole.UserRole, path)
        names = package.list_collection_fonts(path)
        if names is None:
            root.setText(0, f"{os.path.basename(path)}（读取失败）")
            root.setForeground(0, Qt.GlobalColor.red)
        else:
            for i, name in enumerate(names):
                child = QTreeWidgetItem([name])
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(0, Qt.CheckState.Checked)
                child.setData(0, Qt.ItemDataRole.UserRole, i)
                root.addChild(child)
            root.setExpanded(True)
        self.unpack_tree.addTopLevelItem(root)

    def _set_all_checked(self, checked: bool) -> None:
        for i in range(self.unpack_tree.topLevelItemCount()):
            root = self.unpack_tree.topLevelItem(i)
            for j in range(root.childCount()):
                root.child(j).setCheckState(
                    0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def _on_unpack_remove(self):
        for item in self.unpack_tree.selectedItems():
            parent = item.parent()
            if parent is None:
                self.unpack_tree.takeTopLevelItem(self.unpack_tree.indexOfTopLevelItem(item))
            else:
                parent.removeChild(item)

    def _collect_unpack_jobs(self) -> list[tuple[str, list[int]]]:
        jobs: list[tuple[str, list[int]]] = []
        for i in range(self.unpack_tree.topLevelItemCount()):
            root = self.unpack_tree.topLevelItem(i)
            path = root.data(0, Qt.ItemDataRole.UserRole)
            indices = [
                root.child(j).data(0, Qt.ItemDataRole.UserRole)
                for j in range(root.childCount())
                if root.child(j).checkState(0) == Qt.CheckState.Checked
            ]
            if indices:
                jobs.append((path, indices))
        return jobs

    def _run_unpack(self):
        jobs = self._collect_unpack_jobs()
        if not jobs:
            InfoBar.warning("没有可解包的字体", "请先添加集合文件并勾选子字体。", parent=self.window(),
                            position=InfoBarPosition.TOP, duration=3000)
            return
        out_dir = self.unpack_out_dir.text()
        if not out_dir:
            InfoBar.warning("未选择输出目录", "请先选择输出目录。", parent=self.window(),
                            position=InfoBarPosition.TOP, duration=3000)
            return
        self._start_worker(UnpackWorker(jobs, out_dir, self), self._on_unpack_finished)

    def _on_unpack_finished(self, outputs, errors):
        if errors:
            InfoBar.error("解包完成（部分失败）", f"{len(errors)} 个子字体解包失败：{errors[0][0]}",
                          parent=self.window(), position=InfoBarPosition.TOP, duration=4000)
        if outputs:
            InfoBar.success("解包完成", f"已输出 {len(outputs)} 个文件到 {os.path.dirname(outputs[0])}",
                            parent=self.window(), position=InfoBarPosition.TOP, duration=4000)
        if not outputs and not errors:
            InfoBar.warning("没有输出", "勾选的子字体为空，或已全部失败。", parent=self.window(),
                            position=InfoBarPosition.TOP, duration=3000)

    # ---------------------------------------------------------------- 打包面板

    def _build_pack_panel(self) -> QWidget:
        panel = QWidget(self)
        panel.setObjectName("PackPanel")
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 8, 0, 0)

        top = QHBoxLayout()
        self.pack_add = PushButton(FIF.FOLDER_ADD, "添加字体文件", panel)
        self.pack_add.clicked.connect(self._on_pack_add)
        self.pack_remove = PushButton(FIF.DELETE, "移除选中", panel)
        self.pack_remove.clicked.connect(self._on_pack_remove)
        top.addWidget(self.pack_add)
        top.addWidget(self.pack_remove)
        top.addStretch(1)
        v.addLayout(top)

        self.pack_list = ListWidget(panel)
        v.addWidget(self.pack_list, 1)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.addWidget(BodyLabel("输出目录", panel), 0, 0)
        self.pack_out_dir = LineEdit(panel)
        self.pack_out_dir.setReadOnly(True)
        browse = PushButton("浏览…", panel)
        browse.clicked.connect(lambda: self._pick_out_dir(self.pack_out_dir))
        grid.addWidget(self.pack_out_dir, 0, 1)
        grid.addWidget(browse, 0, 2)

        grid.addWidget(BodyLabel("文件名", panel), 1, 0)
        self.pack_name = LineEdit(panel)
        self.pack_name.setText("collection")
        self._pack_name_manual = False
        self.pack_name.textEdited.connect(lambda: setattr(self, "_pack_name_manual", True))
        grid.addWidget(self.pack_name, 1, 1)

        grid.addWidget(BodyLabel("格式", panel), 2, 0)
        self.pack_format = ComboBox(panel)
        self.pack_format.addItem("自动（含 CFF → otc，否则 ttc）", "auto")
        self.pack_format.addItem("强制 .ttc", "ttc")
        self.pack_format.addItem("强制 .otc", "otc")
        grid.addWidget(self.pack_format, 2, 1)
        grid.setColumnStretch(1, 1)
        v.addLayout(grid)

        run_row = QHBoxLayout()
        run_row.addStretch(1)
        self.pack_run = PrimaryPushButton(FIF.PLAY, "开始打包", panel)
        self.pack_run.clicked.connect(self._run_pack)
        run_row.addWidget(self.pack_run)
        v.addLayout(run_row)
        return panel

    def _on_pack_add(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择字体文件", option.import_dir.value, "字体文件 (*.ttf *.otf)")
        if not files:
            return
        qconfig.set(option.import_dir, os.path.dirname(files[0]))
        existing = {self.pack_list.item(i).text() for i in range(self.pack_list.count())}
        for path in files:
            if path not in existing:
                self.pack_list.addItem(QListWidgetItem(path))
                existing.add(path)
        self._update_pack_name_default()

    def _on_pack_remove(self):
        for item in self.pack_list.selectedItems():
            self.pack_list.takeItem(self.pack_list.row(item))
        self._update_pack_name_default()

    def _update_pack_name_default(self) -> None:
        """按所选字体中 Regular 的家族名刷新默认文件名（用户手改后不再覆盖）。"""
        if self._pack_name_manual:
            return
        files = [self.pack_list.item(i).text() for i in range(self.pack_list.count())]
        self.pack_name.setText(package.recommend_pack_name(files) or "collection")

    def _run_pack(self):
        files = [self.pack_list.item(i).text() for i in range(self.pack_list.count())]
        if not files:
            InfoBar.warning("没有字体文件", "请先添加要打包的字体文件。", parent=self.window(),
                            position=InfoBarPosition.TOP, duration=3000)
            return
        out_dir = self.pack_out_dir.text()
        if not out_dir:
            InfoBar.warning("未选择输出目录", "请先选择输出目录。", parent=self.window(),
                            position=InfoBarPosition.TOP, duration=3000)
            return
        out_name = self.pack_name.text().strip() or "collection"
        fmt = self.pack_format.currentData() or "auto"
        self._start_worker(PackWorker(files, out_dir, out_name, fmt, self), self._on_pack_finished)

    def _on_pack_finished(self, out_path, errors):
        if out_path:
            InfoBar.success("打包完成", os.path.basename(out_path),
                            parent=self.window(), position=InfoBarPosition.TOP, duration=4000)
            # 打包成功：清除已选字体列表，文件名恢复默认（未手改标记），下一轮直接开始
            self.pack_list.clear()
            self._pack_name_manual = False
            self._update_pack_name_default()
        if errors:
            InfoBar.error("打包完成（部分失败）", f"{len(errors)} 个文件打包失败：{errors[0][0]}",
                          parent=self.window(), position=InfoBarPosition.TOP, duration=4000)

    # ---------------------------------------------------------------- 公共

    def _pick_out_dir(self, edit: LineEdit) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录", edit.text() or option.package_out_dir.value)
        if folder:
            edit.setText(folder)
            qconfig.set(option.package_out_dir, folder)

    def _start_worker(self, worker, on_finished):
        if self._worker is not None:
            return
        self._worker = worker
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # 不确定进度
        self._set_busy(True)
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
        self.status_label.setText("")
        self._set_busy(False)
        self._worker = None

    def _set_busy(self, busy: bool) -> None:
        for btn in (self.unpack_add, self.unpack_check_all, self.unpack_check_none,
                    self.unpack_remove, self.unpack_run,
                    self.pack_add, self.pack_remove, self.pack_run):
            btn.setEnabled(not busy)
