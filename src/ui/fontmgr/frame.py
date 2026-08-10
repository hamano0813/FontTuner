"""字体管理页：树形查看文件夹里的字体，勾选注册到 Windows（会话级），系统已装字体标记。

会话级注册：勾选即 AddFontResourceEx 加入系统字体表，全会话应用可枚举；取消即注销。
系统已装字体（注册表 Fonts 键 / Windows\\Fonts）在树里灰显标记，不提供勾选，避免误卸。
"""

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QTreeWidgetItem,
    QVBoxLayout,
)
from qfluentwidgets import (
    CaptionLabel,
    Dialog,
    FluentIcon as FIF,
    FolderListSettingCard,
    InfoBar,
    InfoBarPosition,
    ProgressBar,
    PushButton,
    SearchLineEdit,
    SubtitleLabel,
    TreeWidget,
    isDarkTheme,
    qconfig,
)

from config import option
from core import font_register
from ui.fontmgr.worker import RegisterWorker, ScanWorker


class FontFoldersCard(FolderListSettingCard):
    """字体库文件夹卡：管理字体管理页持久化的扫描目录列表，头部含添加与重新扫描按钮。"""

    rescanRequested = Signal()  # 点击「重新扫描」时发出，由页面触发重扫

    def __init__(self, parent=None):
        super().__init__(
            option.fontmgr_folders, "字体库文件夹",
            "字体管理页扫描的目录列表，改动后自动重新加载。",
            directory=option.import_dir.value, parent=parent,
        )
        self.addFolderButton.setText("添加文件夹")
        # 头部：添加按钮右侧再放一个「重新扫描」
        self.rescan_button = PushButton(FIF.SYNC, "重新扫描", self)
        self.rescan_button.clicked.connect(self.rescanRequested.emit)
        self.addWidget(self.rescan_button)

    def _FolderListSettingCard__showConfirmDialog(self, item):
        # qfw 默认确认框是英文，这里改为中文（对应 qfw 内部 __showConfirmDialog）
        name = os.path.basename(item.folder.rstrip("\\/"))
        box = Dialog(
            "确认移除文件夹",
            f"将「{name}」从列表移除后，该目录不再自动扫描（目录本身不会被删除）。",
            self.window(),
        )
        box.yesSignal.connect(lambda: self._FolderListSettingCard__removeFolder(item))
        box.exec()


class FontManagerFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("FontManagerFrame")
        self._worker = None
        self._register_worker = None
        self._registered: set[str] = set()  # 本会话内由本工具注册过的字体路径
        self._auto_restored = False         # 启动自动恢复只做一次（后续手动重扫不再套用）

        self.title = SubtitleLabel("字体管理", self)
        self.hint = CaptionLabel(
            "勾选字体即注册到 Windows（当前会话有效，重启后失效）；取消勾选即注销。系统已安装的字体将被标记。", self)

        self.folders_card = FontFoldersCard(self)  # 字体库目录卡：增删目录 + 重新扫描
        self.folders_card.rescanRequested.connect(self._on_rescan)

        self.tree = TreeWidget(self)
        self.tree.setColumnCount(1)
        self.tree.setHeaderLabels(["字体文件（勾选即注册到 Windows）"])
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.currentItemChanged.connect(self._on_current_item_changed)

        # 筛选框：按名称/家族名过滤树内容（QTreeWidgetItem 重勾选/三态，手动 show/hide 过滤）
        self.filter_edit = SearchLineEdit(self)
        self.filter_edit.setPlaceholderText("筛选字体…")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self._apply_filter)

        # 底部预览：4 行（简/繁/日/英），用选中字体渲染 option.preview_sample
        self.preview_title = CaptionLabel("预览", self)
        self.preview_label = QLabel(self)
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(52)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.preview_label.setText("（请在树中选择要预览的字体）")
        self._preview_family: str | None = None
        self._preview_font_id: int | None = None
        option.preview_sample.valueChanged.connect(self._render_preview)
        option.preview_font_size.valueChanged.connect(self._render_preview)

        self.status_label = CaptionLabel("", self)

        self.progress = ProgressBar(self)
        self.progress.setVisible(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.hint)
        layout.addSpacing(8)
        layout.addWidget(self.folders_card)
        layout.addWidget(self.tree, 1)
        filter_row = QHBoxLayout()
        filter_row.addWidget(self.filter_edit, 1)  # 撑满可用宽度
        self.save_sel_button = PushButton(FIF.SAVE, "保存选中", self)
        self.save_sel_button.setToolTip("把当前勾选的字体保存下来，供以后恢复")
        self.save_sel_button.clicked.connect(self._on_save_selection)
        self.restore_sel_button = PushButton(FIF.HISTORY, "恢复选中", self)
        self.restore_sel_button.setToolTip("把已保存的勾选状态恢复到树中")
        self.restore_sel_button.clicked.connect(self._on_restore_selection)
        self.deselect_button = PushButton(FIF.CANCEL, "取消选中", self)
        self.deselect_button.setToolTip("取消所有勾选，并注销全部已注册字体")
        self.deselect_button.clicked.connect(self._on_deselect_all)
        filter_row.addWidget(self.save_sel_button)
        filter_row.addWidget(self.restore_sel_button)
        filter_row.addWidget(self.deselect_button)
        layout.addLayout(filter_row)
        layout.addWidget(self.progress)
        layout.addWidget(self.preview_title)
        layout.addWidget(self.preview_label)
        layout.addWidget(self.status_label)
        self.setLayout(layout)

        # 启动时自动扫描持久化的字体库目录（本页字体库卡可管理），无需每次手动载入
        option.fontmgr_folders.valueChanged.connect(self._on_folders_changed)
        if option.fontmgr_folders.value:
            self._start_scan(list(option.fontmgr_folders.value))

    # ---------------------------------------------------------------- 扫描

    def _on_rescan(self):
        folders = list(option.fontmgr_folders.value)
        if folders:
            self._start_scan(folders)

    def _on_folders_changed(self, folders):
        """字体库目录列表变动（设置页/本页添加）：重新扫描。"""
        self._start_scan(list(folders))

    def _start_scan(self, roots: list[str]) -> None:
        if self._worker is not None:
            return
        self._worker = ScanWorker(roots, self)
        self.status_label.setText("扫描中…")
        self.folders_card.rescan_button.setEnabled(False)
        self._worker.finished_ok.connect(self._on_scan_finished)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_scan_finished(self, tree, errors):
        self.tree.blockSignals(True)
        self.tree.clear()
        for node in tree:
            root = self._build_item(node)
            self.tree.addTopLevelItem(root)
            self._recompute_dir_states(root)  # 按叶子勾选态回填目录三态
        self.tree.blockSignals(False)
        self._apply_filter(self.filter_edit.text())  # 重新套用筛选
        # 首次扫描完成且开启自动恢复：把保存的选中恢复到树中（重新注册）
        if (not self._auto_restored and option.fontmgr_auto_restore.value
                and option.fontmgr_saved_selection.value):
            self._auto_restored = True
            self._restore_selection(set(option.fontmgr_saved_selection.value))
        self.status_label.setText(f"已加载 {len(tree)} 个文件夹，勾选字体即可注册到 Windows。")
        if errors:
            InfoBar.error("部分文件夹扫描失败", f"{len(errors)} 个文件夹：{errors[0][0]}",
                          parent=self.window(), position=InfoBarPosition.TOP, duration=4000)

    def _on_worker_finished(self):
        self.folders_card.rescan_button.setEnabled(True)
        self._worker = None

    def _apply_filter(self, text: str) -> None:
        """按名称/家族名过滤树：隐藏不匹配节点，目录在无匹配子项时隐藏。"""
        text = (text or "").strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            self._filter_item(self.tree.topLevelItem(i), text)

    def _filter_item(self, item, text: str) -> bool:
        """返回该节点是否可见（自身或后代匹配），并递归设置隐藏。

        注意：必须遍历全部子项以逐一 setHidden，不能用 any() 短路。
        """
        self_match = not text or text in item.text(0).lower() or text in (item.toolTip(0) or "").lower()
        if item.childCount() > 0:
            child_visible = False
            for i in range(item.childCount()):
                if self._filter_item(item.child(i), text):
                    child_visible = True
            visible = self_match or child_visible
        else:
            visible = self_match
        item.setHidden(not visible)
        return visible

    def _build_item(self, node: dict) -> QTreeWidgetItem:
        item = QTreeWidgetItem([node["name"]])
        item.setData(0, Qt.ItemDataRole.UserRole, node["path"])
        if node["is_font"] and node["installed"]:
            # 系统已装：灰显标记，不提供勾选，避免误卸系统字体
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            item.setText(0, f"{node['name']}（系统已安装）")
            item.setForeground(0, QColor("#8a8a8a"))
            item.setToolTip(0, f"{node['family'] or node['name']} — 已由系统安装，无需注册")
        else:
            # 目录与可注册字体：都提供勾选框（目录勾选 = 整目录批量注册）
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            if node["is_font"]:
                item.setCheckState(
                    0, Qt.CheckState.Checked if node["path"] in self._registered else Qt.CheckState.Unchecked)
                item.setToolTip(0, node["family"] or node["name"])
        for child in node.get("children", []):
            item.addChild(self._build_item(child))
        return item

    # ---------------------------------------------------------------- 注册/注销

    def _on_item_changed(self, item, column):
        if column != 0:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return
        state = item.checkState(0)
        if item.childCount() > 0:
            # 目录：把勾选态传播到整棵子树，再统一注册/注销（只弹一条汇总）
            if state == Qt.CheckState.Checked:
                self._set_descendants_checked(item, True)
                self._sync_registration()
            elif state == Qt.CheckState.Unchecked:
                self._set_descendants_checked(item, False)
                self._sync_registration()
            # PartiallyChecked 是程序回填的展示态，不响应
        elif item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
            self._toggle_font(item, state == Qt.CheckState.Checked)
        else:
            return  # 已装字体不可勾选
        self._update_ancestors(item)
        self._update_status()

    def _toggle_font(self, item, checked: bool) -> None:
        """单个字体叶子勾选/取消：注册/注销该字体。"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if checked:
            if font_register.register_font(path):
                is_new = path not in self._registered
                self._registered.add(path)
                if is_new:
                    InfoBar.success("已注册", f"{os.path.basename(path)} 已注册到 Windows",
                                    parent=self.window(), position=InfoBarPosition.TOP, duration=2500)
            else:
                item.setCheckState(0, Qt.CheckState.Unchecked)  # 失败回滚
                InfoBar.error("注册失败", f"{os.path.basename(path)} 无法注册（文件可能已损坏）",
                              parent=self.window(), position=InfoBarPosition.TOP, duration=3000)
        else:
            if path in self._registered:
                if font_register.unregister_font(path):
                    self._registered.discard(path)
                    InfoBar.success("已注销", f"{os.path.basename(path)} 已从 Windows 注销",
                                    parent=self.window(), position=InfoBarPosition.TOP, duration=2500)
                else:
                    item.setCheckState(0, Qt.CheckState.Checked)  # 失败回滚（正被占用）
                    InfoBar.warning("注销失败", f"{os.path.basename(path)} 正被占用，无法注销",
                                    parent=self.window(), position=InfoBarPosition.TOP, duration=3000)

    def _set_descendants_checked(self, dir_item, checked: bool) -> None:
        """把目录勾选态批量写到整棵子树（阻塞信号，避免逐项触发注册）。"""
        self.tree.blockSignals(True)
        self._set_descendants_recursive(dir_item, checked)
        self.tree.blockSignals(False)

    def _set_descendants_recursive(self, item, checked: bool) -> None:
        for i in range(item.childCount()):
            child = item.child(i)
            if child.childCount() > 0:
                child.setCheckState(
                    0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                self._set_descendants_recursive(child, checked)
            elif child.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                child.setCheckState(
                    0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def _collect_checked_fonts(self) -> set[str]:
        """遍历整棵树，收集所有已勾选的字体叶子路径。"""
        checked: set[str] = set()

        def walk(item):
            for i in range(item.childCount()):
                child = item.child(i)
                if child.childCount() > 0:
                    walk(child)
                elif (child.flags() & Qt.ItemFlag.ItemIsUserCheckable
                      and child.checkState(0) == Qt.CheckState.Checked):
                    path = child.data(0, Qt.ItemDataRole.UserRole)
                    if path:
                        checked.add(path)

        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))
        return checked

    # ---------------------------------------------------------------- 选中持久化

    def _on_save_selection(self):
        """把当前勾选的字体路径保存到配置（供「恢复选中」与启动自动恢复使用）。"""
        checked = self._collect_checked_fonts()
        qconfig.set(option.fontmgr_saved_selection, sorted(checked))
        InfoBar.success("已保存选中", f"已保存 {len(checked)} 个字体，可随时用「恢复选中」还原。",
                        parent=self.window(), position=InfoBarPosition.TOP, duration=3000)

    def _on_restore_selection(self):
        """按已保存的路径恢复勾选态并同步注册。"""
        saved = list(option.fontmgr_saved_selection.value)
        if not saved:
            InfoBar.warning("没有已保存的选中", "请先勾选字体并点击「保存选中」。",
                            parent=self.window(), position=InfoBarPosition.TOP, duration=3000)
            return
        if self.tree.topLevelItemCount() == 0:
            InfoBar.warning("没有字体", "当前没有已加载的字体，请先添加字体库文件夹。",
                            parent=self.window(), position=InfoBarPosition.TOP, duration=3000)
            return
        self._restore_selection(set(saved))

    def _on_deselect_all(self):
        """取消全部勾选，并注销所有已注册字体。"""
        if self.tree.topLevelItemCount() == 0:
            return
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            self._set_descendants_recursive(self.tree.topLevelItem(i), False)
            self._recompute_dir_states(self.tree.topLevelItem(i))
        self.tree.blockSignals(False)
        self._sync_registration()
        self._update_status()

    def _restore_selection(self, paths: set[str]) -> None:
        """把勾选态恢复为 paths（精确匹配，未在保存列表中的一律取消）。

        路径先归一化（大小写/斜杠），避免跨会话保存的路径格式与扫描结果不一致。
        阻塞信号逐个设置叶子，最后统一走 _sync_registration 批量注册/注销。
        """
        paths = {os.path.normcase(os.path.abspath(p)) for p in paths}
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            self._apply_saved_checked(self.tree.topLevelItem(i), paths)
            self._recompute_dir_states(self.tree.topLevelItem(i))
        self.tree.blockSignals(False)
        self._sync_registration()
        self._update_status()

    def _apply_saved_checked(self, item, paths: set[str]) -> None:
        """递归：字体叶子按 paths 勾选/取消；目录节点不动，稍后统一回填三态。"""
        for i in range(item.childCount()):
            child = item.child(i)
            if child.childCount() > 0:
                self._apply_saved_checked(child, paths)
            elif child.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                path = child.data(0, Qt.ItemDataRole.UserRole)
                key = os.path.normcase(os.path.abspath(path)) if path else ""
                child.setCheckState(
                    0, Qt.CheckState.Checked if key in paths else Qt.CheckState.Unchecked)

    def _sync_registration(self) -> None:
        """按当前树勾选态与 _registered 的差集批量注册/注销（后台线程，避免大量注册卡界面）。"""
        checked = self._collect_checked_fonts()
        to_register = checked - self._registered
        to_unregister = self._registered - checked
        if not to_register and not to_unregister:
            self._update_status()
            return
        self._start_register(to_register, to_unregister)

    def _start_register(self, to_register, to_unregister) -> None:
        if self._register_worker is not None:
            return
        worker = RegisterWorker(to_register, to_unregister, self)
        self._register_worker = worker
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self._set_busy(True)
        worker.progress.connect(self._on_register_progress)
        worker.finished_ok.connect(self._on_register_finished)
        worker.finished.connect(self._on_register_worker_done)
        worker.start()

    def _on_register_progress(self, done, total):
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
            self.status_label.setText(f"正在更新字体注册 {done}/{total}")

    def _on_register_finished(self, registered, unregistered, errors):
        self._registered.update(registered)
        self._registered.difference_update(unregistered)
        # 注册失败的字体回滚勾选态，并回填目录三态
        failed_paths = {p for p, _ in errors}
        if failed_paths:
            self.tree.blockSignals(True)
            self._uncheck_paths(failed_paths)
            for i in range(self.tree.topLevelItemCount()):
                self._recompute_dir_states(self.tree.topLevelItem(i))
            self.tree.blockSignals(False)
        parts = []
        if registered:
            parts.append(f"已注册 {len(registered)} 个字体")
        if unregistered:
            parts.append(f"已注销 {len(unregistered)} 个字体")
        if errors:
            parts.append(f"{len(errors)} 个失败")
        if parts:
            InfoBar.info("字体注册已更新", "，".join(parts), parent=self.window(),
                         position=InfoBarPosition.TOP, duration=2500)
        self._update_status()

    def _on_register_worker_done(self):
        self.progress.setVisible(False)
        self.status_label.setText(f"已注册 {len(self._registered)} 个字体（当前会话有效，重启后失效）")
        self._set_busy(False)
        self._register_worker = None

    def _set_busy(self, busy: bool) -> None:
        self.tree.setEnabled(not busy)
        self.folders_card.rescan_button.setEnabled(not busy)
        self.save_sel_button.setEnabled(not busy)
        self.restore_sel_button.setEnabled(not busy)
        self.deselect_button.setEnabled(not busy)

    def _uncheck_paths(self, paths: set[str]) -> None:
        def walk(item):
            for i in range(item.childCount()):
                child = item.child(i)
                if child.childCount() > 0:
                    walk(child)
                elif child.data(0, Qt.ItemDataRole.UserRole) in paths:
                    child.setCheckState(0, Qt.CheckState.Unchecked)

        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))

    def _update_ancestors(self, item) -> None:
        """自底向上刷新祖先目录的三态（部分勾选显示半选）。"""
        self.tree.blockSignals(True)
        parent = item.parent()
        while parent is not None:
            checkable = [parent.child(i) for i in range(parent.childCount())
                         if parent.child(i).flags() & Qt.ItemFlag.ItemIsUserCheckable]
            if checkable:
                if all(c.checkState(0) == Qt.CheckState.Checked for c in checkable):
                    parent.setCheckState(0, Qt.CheckState.Checked)
                elif all(c.checkState(0) == Qt.CheckState.Unchecked for c in checkable):
                    parent.setCheckState(0, Qt.CheckState.Unchecked)
                else:
                    parent.setCheckState(0, Qt.CheckState.PartiallyChecked)
            parent = parent.parent()
        self.tree.blockSignals(False)

    def _recompute_dir_states(self, item) -> None:
        """自底向上按子项勾选态刷新目录节点三态。"""
        for i in range(item.childCount()):
            self._recompute_dir_states(item.child(i))
        if item.childCount() == 0:
            return
        checkable = [item.child(i) for i in range(item.childCount())
                     if item.child(i).flags() & Qt.ItemFlag.ItemIsUserCheckable]
        if not checkable:
            return
        if all(c.checkState(0) == Qt.CheckState.Checked for c in checkable):
            item.setCheckState(0, Qt.CheckState.Checked)
        elif all(c.checkState(0) == Qt.CheckState.Unchecked for c in checkable):
            item.setCheckState(0, Qt.CheckState.Unchecked)
        else:
            item.setCheckState(0, Qt.CheckState.PartiallyChecked)

    def _update_status(self) -> None:
        self.status_label.setText(f"已注册 {len(self._registered)} 个字体（当前会话有效，重启后失效）")

    # ---------------------------------------------------------------- 底部预览

    def _on_current_item_changed(self, current, previous):
        """选中字体叶子时用该字体渲染 4 行预览文字。"""
        if current is None:
            self._clear_preview()
            return
        path = current.data(0, Qt.ItemDataRole.UserRole)
        is_font_leaf = current.childCount() == 0 and current.flags() & Qt.ItemFlag.ItemIsUserCheckable
        if not path or not is_font_leaf:
            self._clear_preview()
            return
        self._preview_font(path)

    def _preview_font(self, path: str) -> None:
        """进程内注册字体（QFontDatabase）并取家族名，供渲染预览。"""
        if self._preview_font_id is not None:
            QFontDatabase.removeApplicationFont(self._preview_font_id)
            self._preview_font_id = None
        fam_id = QFontDatabase.addApplicationFont(path)
        if fam_id == -1:
            self._preview_family = None
            self.preview_label.setText("（该字体无法预览）")
            return
        self._preview_font_id = fam_id
        families = QFontDatabase.applicationFontFamilies(fam_id)
        self._preview_family = families[0] if families else None
        self._render_preview()

    def _render_preview(self) -> None:
        color = "white" if isDarkTheme() else "black"
        self.preview_label.setStyleSheet(f"color: {color};")
        if not self._preview_family:
            self.preview_label.setText("（该字体无法预览）")
            return
        text = option.preview_sample.value or " "
        self.preview_label.setFont(QFont(self._preview_family, option.preview_font_size.value))
        self.preview_label.setText(text)

    def _clear_preview(self) -> None:
        if self._preview_font_id is not None:
            QFontDatabase.removeApplicationFont(self._preview_font_id)
            self._preview_font_id = None
        self._preview_family = None
        self.preview_label.setText("（请在树中选择要预览的字体）")
