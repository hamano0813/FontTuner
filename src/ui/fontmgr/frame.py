"""字体管理页：树形查看文件夹里的字体，勾选注册到 Windows（会话级），系统已装字体标记。

会话级注册：勾选即 AddFontResourceEx 加入系统字体表，全会话应用可枚举；取消即注销。
系统已装字体（注册表 Fonts 键 / Windows\\Fonts）在树里灰显标记，不提供勾选，避免误卸。
右键可把字体「安装到当前用户」（复制 + HKCU 注册表，DirectWrite 应用如 Terminal/VS Code
也能用），已安装字体灰显、右键可「取消安装」。
"""

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontDatabase
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTreeWidgetItem,
    QVBoxLayout,
)
from qfluentwidgets import (
    Action,
    CaptionLabel,
    Dialog,
    FluentIcon as FIF,
    FolderListSettingCard,
    InfoBar,
    InfoBarPosition,
    MessageBox,
    ProgressBar,
    PushButton,
    RoundMenu,
    SearchLineEdit,
    SubtitleLabel,
    TreeWidget,
    isDarkTheme,
    qconfig,
)

from config import option
from core import font_register, subtitle_font
from ui.fontmgr.subtitle_dialog import SubtitleFontDialog
from ui.fontmgr.worker import RegisterWorker, ScanWorker, UserFontWorker


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
        self._partial_scan = False          # 当前扫描是否仅针对选中项（部分重扫）
        self._register_worker = None
        self._userfont_worker = None
        self._registered: set[str] = set()  # 本会话内由本工具注册过的字体路径
        self._auto_restored = False         # 启动自动恢复只做一次（后续手动重扫不再套用）
        self._userfont_item_map: dict = {}  # 批量安装/卸载时 库路径 -> 树节点，线程返回后回填

        self.title = SubtitleLabel("字体管理", self)
        self.hint = CaptionLabel(
            "勾选字体即注册到 Windows（当前会话有效，重启后失效）；取消勾选即注销。系统已安装的字体将被标记。", self)

        self.folders_card = FontFoldersCard(self)  # 字体库目录卡：增删目录 + 重新扫描
        self.folders_card.rescanRequested.connect(self._on_rescan)

        self.tree = TreeWidget(self)
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["字体文件（勾选即注册到 Windows）", "Windows 标准字体名"])
        header = self.tree.header()
        header.setStretchLastSection(False)
        # 两列等宽：都走 Stretch，随窗口缩放始终保持 1:1
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.currentItemChanged.connect(self._on_current_item_changed)
        # 多选 + 右键菜单：批量安装/取消安装到当前用户（勾选框仍负责会话级注册）
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_context_menu)

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
        self.subtitle_button = PushButton(FIF.VIDEO, "字幕适配", self)
        self.subtitle_button.setToolTip("选择 .ass/.ssa 字幕，把其中用到的字体名批量替换为当前字体库中的字体")
        self.subtitle_button.clicked.connect(self._on_subtitle_adapt)
        filter_row.addWidget(self.subtitle_button)
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
        """重新扫描（硬扫描）：有选中项则只重扫选中项，无选中则全表重扫。

        硬扫描跳过 mtime/size 缓存，已存在的字体文件也强制重读名称并更新缓存。
        """
        selected = self.tree.selectedItems()
        if selected:
            paths: list[str] = []
            seen: set[str] = set()
            for item in selected:
                path = item.data(0, Qt.ItemDataRole.UserRole)
                if not path and item.parent() is not None:
                    # TTC/OTC face 子节点不可单独重扫：归到其母节点（整个集合文件）
                    path = item.parent().data(0, Qt.ItemDataRole.UserRole)
                if path and path not in seen:
                    seen.add(path)
                    paths.append(path)
            if paths:
                self._start_scan(paths, partial=True, hard=True)
            return
        folders = list(option.fontmgr_folders.value)
        if folders:
            self._start_scan(folders, hard=True)

    def _on_folders_changed(self, folders):
        """字体库目录列表变动（设置页/本页添加）：重新扫描（非硬扫描，走缓存）。"""
        self._start_scan(list(folders))

    def _start_scan(self, roots: list[str], partial: bool = False, hard: bool = False) -> None:
        if self._worker is not None:
            return
        self._worker = ScanWorker(roots, self, hard=hard)
        self._partial_scan = partial
        self.status_label.setText("扫描中…")
        self.folders_card.rescan_button.setEnabled(False)
        self._worker.finished_ok.connect(self._on_scan_finished)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_scan_finished(self, tree, errors):
        if self._partial_scan:
            self._apply_partial_scan(tree)
        else:
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
            kind = "项" if self._partial_scan else "文件夹"
            InfoBar.error(f"部分{kind}扫描失败", f"{len(errors)} 个{kind}：{errors[0][0]}",
                          parent=self.window(), position=InfoBarPosition.TOP, duration=4000)

    def _items_by_path(self) -> dict[str, QTreeWidgetItem]:
        """遍历整棵树，收集 path → 树节点 的映射（face 子节点 path 为空，不入映射）。"""
        m: dict[str, QTreeWidgetItem] = {}

        def walk(item):
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path:
                m[os.path.normcase(os.path.abspath(path))] = item
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))
        return m

    def _apply_partial_scan(self, nodes) -> None:
        """把部分扫描的节点原位替换到树中：目录整棵重建、字体文件单读替换。

        只动选中项对应节点，其余子树不重建；保持展开态、重算目录三态、套用筛选。
        """
        items_by_path = self._items_by_path()
        replaced = 0
        for node in nodes:
            path = node.get("path")
            if not path:
                continue
            key = os.path.normcase(os.path.abspath(path))
            item = items_by_path.get(key)
            if item is None:
                continue
            expanded = item.isExpanded()
            parent = item.parent()
            self.tree.blockSignals(True)
            new_item = self._build_item(node)
            if parent is None:
                idx = self.tree.indexOfTopLevelItem(item)
                self.tree.takeTopLevelItem(idx)
                self.tree.insertTopLevelItem(idx, new_item)
            else:
                idx = parent.indexOfChild(item)
                parent.takeChild(idx)
                parent.insertChild(idx, new_item)
            new_item.setExpanded(expanded)
            self._recompute_dir_states(new_item)  # 按叶子勾选态回填目录三态
            self.tree.blockSignals(False)
            self._update_ancestors(new_item)  # 刷新祖先目录三态
            # 该节点整棵重建后，其下后代已被覆盖，后续选中后代节点跳过
            prefix = key + os.sep
            for k in [k for k in items_by_path if k.startswith(prefix)]:
                del items_by_path[k]
            replaced += 1
        self._apply_filter(self.filter_edit.text())
        self._update_status()
        self.status_label.setText(f"已重新扫描 {replaced} 项")

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
        self_match = (not text
                      or text in item.text(0).lower()
                      or text in item.text(1).lower()
                      or text in (item.toolTip(0) or "").lower())
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
        win_name = node.get("win_name") or ""
        item = QTreeWidgetItem([node["name"], win_name])
        # 目录用文件夹图标，字体（含 TTC/OTC 与其 face 子节点）用字体图标，便于区分
        is_font = node["is_font"] or node.get("is_font_face")
        item.setIcon(0, FIF.FONT.icon() if is_font else FIF.FOLDER.icon())
        item.setData(0, Qt.ItemDataRole.UserRole, node["path"])
        item.setData(0, Qt.ItemDataRole.UserRole + 1, node.get("family") or "")
        item.setData(0, Qt.ItemDataRole.UserRole + 3, bool(node.get("installed")))
        item.setData(0, Qt.ItemDataRole.UserRole + 4, win_name)  # Windows 标准字体名
        item.setData(0, Qt.ItemDataRole.UserRole + 5, node.get("en_name") or "")  # 英文系统名（隐藏匹配词）
        item.setData(0, Qt.ItemDataRole.UserRole + 6, bool(node.get("is_font")))  # 是否字体文件
        installed_user_path = node.get("installed_user_path") or ""
        if node.get("is_font_face"):
            # TTC/OTC 内的 face 子节点：仅展示，不可勾选（只能勾选整个集合文件）
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            item.setToolTip(0, win_name or node["family"] or node["name"])
            item.setForeground(0, QColor("#9a9a9a"))  # 弱化，区别于可注册项
        elif node["is_font"] and node["installed"]:
            # 系统已装：灰显标记，不提供勾选，避免误卸系统字体
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            item.setText(0, f"{node['name']}（系统已安装）")
            item.setForeground(0, QColor("#8a8a8a"))
            item.setToolTip(0, f"{win_name or node['family'] or node['name']} — 已由系统安装，无需注册")
        elif node["is_font"] and installed_user_path:
            # 本工具安装到当前用户：灰显不可勾选，右键可取消安装
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            item.setText(0, f"{node['name']}（已安装到当前用户）")
            item.setForeground(0, QColor("#8a8a8a"))
            item.setToolTip(0, f"{win_name or node['family'] or node['name']} — 已安装到当前用户，可直接使用")
            item.setData(0, Qt.ItemDataRole.UserRole + 2, installed_user_path)
        else:
            # 目录与可注册字体：都提供勾选框（目录勾选 = 整目录批量注册）
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            if node["is_font"]:
                item.setCheckState(
                    0, Qt.CheckState.Checked if node["path"] in self._registered else Qt.CheckState.Unchecked)
                item.setToolTip(0, win_name or node["family"] or node["name"])
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
        if item.childCount() > 0 and not item.data(0, Qt.ItemDataRole.UserRole + 6):
            # 目录（非字体文件）：把勾选态传播到整棵子树，再统一注册/注销（只弹一条汇总）
            if state == Qt.CheckState.Checked:
                self._set_descendants_checked(item, True)
                self._sync_registration()
            elif state == Qt.CheckState.Unchecked:
                self._set_descendants_checked(item, False)
                self._sync_registration()
            # PartiallyChecked 是程序回填的展示态，不响应
        elif item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
            # 字体文件（含 TTC/OTC 整体）：勾选即注册整个文件
            self._toggle_font(item, state == Qt.CheckState.Checked)
        else:
            return  # 已装字体/face 子节点不可勾选
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
        """遍历整棵树，收集所有已勾选的字体文件路径（含 TTC/OTC 整体勾选，目录除外）。"""
        checked: set[str] = set()

        def walk(item):
            for i in range(item.childCount()):
                child = item.child(i)
                if child.childCount() > 0:
                    walk(child)
                if (child.flags() & Qt.ItemFlag.ItemIsUserCheckable
                        and child.checkState(0) == Qt.CheckState.Checked
                        and child.data(0, Qt.ItemDataRole.UserRole + 6)):
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

    # ---------------------------------------------------------------- 字幕字体适配

    def _collect_library_font_names(self) -> list[tuple[str, str]]:
        """当前字体库全部字体名：[(win_name, en_name), …] 按显示名去重排序。

        win_name 作下拉显示项，en_name（英文系统名）作隐藏匹配词。
        """
        seen: dict[str, str] = {}  # win_name -> en_name
        for i in range(self.tree.topLevelItemCount()):
            self._collect_item_font_names(self.tree.topLevelItem(i), seen)
        return sorted(seen.items())

    def _collect_item_font_names(self, item, seen: dict[str, str]) -> None:
        for i in range(item.childCount()):
            child = item.child(i)
            if child.childCount() > 0:
                self._collect_item_font_names(child, seen)
            else:
                en = child.data(0, Qt.ItemDataRole.UserRole + 5) or ""
                family = child.data(0, Qt.ItemDataRole.UserRole + 1) or ""
                win = child.data(0, Qt.ItemDataRole.UserRole + 4) or family
                if win:
                    seen.setdefault(win, en)
                # 家族名别名：win_name 已带子家族名（如「微软雅黑 Regular」），
                # 而字幕常只写家族名（如「微软雅黑」），补一项使完全匹配仍可自动预选
                if family and family != win:
                    seen.setdefault(family, en)

    def _check_font_nodes_by_name(self, names: set[str]) -> None:
        """按标准字体名（win_name）或家族名自动勾选对应字体文件节点。

        独立 .ttf/.otf 节点命中则直接勾选；TTC/OTC 内的 face 子节点命中则勾选其
        TTC 母节点（注册整个集合文件）。批量勾选后统一走 _sync_registration 注册。
        """
        if not names:
            return
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            self._check_node_by_name(self.tree.topLevelItem(i), names)
        for i in range(self.tree.topLevelItemCount()):
            self._recompute_dir_states(self.tree.topLevelItem(i))
        self.tree.blockSignals(False)
        self._sync_registration()

    def _check_node_by_name(self, item, names: set[str]) -> None:
        """递归勾选：字体文件（含 TTC 整体）按自身 win_name/家族名匹配；face 子节点命中则勾选母节点。"""
        family = item.data(0, Qt.ItemDataRole.UserRole + 1) or ""
        win = item.data(0, Qt.ItemDataRole.UserRole + 4) or family
        hit = win in names or (bool(family) and family in names)
        if item.data(0, Qt.ItemDataRole.UserRole + 6):
            # 独立字体 / TTC 整体：命中即勾选（仅可勾选节点）
            if hit and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(0, Qt.CheckState.Checked)
        elif item.parent() is not None and hit:
            # face 子节点：命中即勾选其母节点（TTC/OTC 整体）
            parent = item.parent()
            if (parent.data(0, Qt.ItemDataRole.UserRole + 6)
                    and parent.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                parent.setCheckState(0, Qt.CheckState.Checked)
        for i in range(item.childCount()):
            self._check_node_by_name(item.child(i), names)

    def _on_subtitle_adapt(self):
        """字幕字体适配：选 .ass/.ssa，把用到的字体名批量替换为当前字体库中的字体。"""
        paths, _ = QFileDialog.getOpenFileNames(
            self.window(), "选择字幕文件（可多选）", "",
            "字幕文件 (*.ass *.ssa);;所有文件 (*.*)")
        if not paths:
            return

        # 收集字幕字体名（跨文件去重）
        ass_fonts: set[str] = set()
        for p in paths:
            try:
                text, _ = subtitle_font.read_subtitle(p)
            except (OSError, UnicodeDecodeError) as exc:
                InfoBar.error("读取失败", f"{os.path.basename(p)}：{exc}",
                              parent=self.window(), position=InfoBarPosition.TOP, duration=4000)
                continue
            ass_fonts.update(subtitle_font.extract_font_names(text))
        if not ass_fonts:
            InfoBar.warning("未找到字体名", "所选字幕中未解析到任何字体名（无 Style 行或 \\fn 标签）。",
                            parent=self.window(), position=InfoBarPosition.TOP, duration=4000)
            return

        library = self._collect_library_font_names()
        if not library:
            InfoBar.warning("字体库为空", "当前没有已加载的字体，无法进行字幕适配。",
                            parent=self.window(), position=InfoBarPosition.TOP, duration=4000)
            return

        dlg = SubtitleFontDialog(sorted(ass_fonts), library, self.window())
        if not dlg.exec():
            return
        mapping = dlg.result_mapping()
        if not mapping:
            InfoBar.info("未做替换", "未选择任何替换字体，字幕保持不变。",
                         parent=self.window(), position=InfoBarPosition.TOP, duration=3000)
            return

        # 自动勾选替换目标字体：独立 .ttf/.otf 直接勾选；TTC/OTC face 命中勾选其母节点；
        # 留空（未替换）的字体不额外勾选任何节点
        self._check_font_nodes_by_name(set(mapping.values()))

        # 批量替换并写回原文件
        changed_files = 0
        total_repl = 0
        for p in paths:
            try:
                text, enc = subtitle_font.read_subtitle(p)
            except (OSError, UnicodeDecodeError) as exc:
                InfoBar.error("读取失败", f"{os.path.basename(p)}：{exc}",
                              parent=self.window(), position=InfoBarPosition.TOP, duration=4000)
                continue
            new_text, n = subtitle_font.apply_replacements(text, mapping)
            if n == 0:
                continue
            try:
                subtitle_font.write_subtitle(p, new_text, enc)
            except (OSError, UnicodeEncodeError) as exc:
                InfoBar.error("写入失败", f"{os.path.basename(p)}：{exc}",
                              parent=self.window(), position=InfoBarPosition.TOP, duration=4000)
                continue
            changed_files += 1
            total_repl += n
        if changed_files:
            InfoBar.success("替换完成", f"共替换 {total_repl} 处字体名，修改 {changed_files} 个文件。",
                            parent=self.window(), position=InfoBarPosition.TOP, duration=4000)

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
        """递归：字体文件（含 TTC/OTC 整体）按 paths 勾选/取消；目录不动，稍后统一回填三态。"""
        for i in range(item.childCount()):
            child = item.child(i)
            if child.childCount() > 0:
                self._apply_saved_checked(child, paths)
            if (child.flags() & Qt.ItemFlag.ItemIsUserCheckable
                    and child.data(0, Qt.ItemDataRole.UserRole + 6)):
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
        self._register_worker = None
        self._set_busy(self._userfont_worker is not None)

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
                if child.data(0, Qt.ItemDataRole.UserRole) in paths:
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

    # ---------------------------------------------------------------- 安装到当前用户

    def _on_tree_context_menu(self, pos):
        """树右键：按选中集合（目录自动展开到字体叶）提供「发送到字体编辑」/安装/取消安装。"""
        item = self.tree.itemAt(pos)
        if item is None:
            return
        if item in self.tree.selectedItems():
            items = self.tree.selectedItems()
        else:  # 右键在选中集之外：以该节点为准
            self.tree.clearSelection()
            item.setSelected(True)
            items = [item]

        to_install: list = []    # (item, path, family)
        to_uninstall: list = []  # (item, family, path)
        seen_paths: set = set()
        seen_families: set = set()

        def walk(it):
            if it.childCount() > 0 and not it.data(0, Qt.ItemDataRole.UserRole + 6):
                # 目录：展开到字体文件；TTC/OTC 整体（is_font）作为单个字体处理
                for i in range(it.childCount()):
                    walk(it.child(i))
                return
            path = it.data(0, Qt.ItemDataRole.UserRole)
            if not path or it.data(0, Qt.ItemDataRole.UserRole + 3):
                return  # face 子节点/系统已装字体不提供安装/卸载
            installed_path = it.data(0, Qt.ItemDataRole.UserRole + 2)
            family = it.data(0, Qt.ItemDataRole.UserRole + 1) or \
                os.path.splitext(os.path.basename(path))[0]
            if installed_path:
                key = ("u", family.lower())
                if key not in seen_families:
                    seen_families.add(key)
                    to_uninstall.append((it, family, path))
            elif it.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                if path not in seen_paths:
                    seen_paths.add(path)
                    to_install.append((it, path, family))

        for it in items:
            walk(it)

        # 收集可发送到编辑器页的字体文件路径（目录展开到字体；TTC/OTC face 归到集合文件）
        to_send: set[str] = set()

        def collect_send(it):
            if it.childCount() > 0 and not it.data(0, Qt.ItemDataRole.UserRole + 6):
                for i in range(it.childCount()):
                    collect_send(it.child(i))
                return
            path = it.data(0, Qt.ItemDataRole.UserRole)
            if not path and it.parent() is not None:
                path = it.parent().data(0, Qt.ItemDataRole.UserRole)
            if path:
                to_send.add(path)

        for it in items:
            collect_send(it)
        sendable = sorted(to_send)

        if not sendable and not to_install and not to_uninstall:
            return
        menu = RoundMenu(parent=self.tree)
        if sendable:
            n = len(sendable)
            act = Action(FIF.EDIT, "发送到字体编辑" if n == 1 else f"发送到字体编辑（{n} 个）", menu)
            act.triggered.connect(lambda: self._send_to_editor(list(sendable)))
            menu.addAction(act)
        if to_install:
            if sendable:
                menu.addSeparator()
            n = len(to_install)
            act = Action(FIF.ADD, "安装到当前用户" if n == 1 else f"安装到当前用户（{n} 个）", menu)
            act.triggered.connect(lambda: self._on_install_to_user(list(to_install)))
            menu.addAction(act)
        if to_uninstall:
            if sendable or to_install:
                menu.addSeparator()
            n = len(to_uninstall)
            act = Action(FIF.DELETE, "取消安装" if n == 1 else f"取消安装（{n} 个）", menu)
            act.triggered.connect(lambda: self._on_uninstall_from_user(list(to_uninstall)))
            menu.addAction(act)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _send_to_editor(self, paths: list[str]):
        """发送到字体编辑：追加到编辑器待编辑表格，InfoBar 提示成功（不跳转页面）。"""
        if not paths:
            return
        editor = getattr(self.window(), "editor_frame", None)
        if editor is None:
            return
        editor.import_paths(paths, append=True)
        n = len(paths)
        InfoBar.success(
            "已发送到字体编辑",
            f"{n} 个字体已追加到编辑表格。" if n > 1 else "已追加 1 个字体到编辑表格。",
            parent=self.window(), position=InfoBarPosition.TOP, duration=3000)

    def _on_install_to_user(self, entries):
        """批量安装到当前用户（单个直接执行；批量先确认）。"""
        if len(entries) > 1:
            names = [os.path.basename(p) for _, p, _ in entries]
            preview = "\n".join(f"· {n}" for n in names[:8]) + ("\n…" if len(names) > 8 else "")
            box = MessageBox(
                "安装到当前用户",
                f"将把 {len(entries)} 个字体安装到当前用户（复制到用户字体目录并注册）：\n{preview}",
                self.window())
            box.yesButton.setText("安装")
            box.cancelButton.setText("取消")
            if not box.exec():
                return
        self._userfont_item_map = {p: it for it, p, _ in entries}
        self._start_userfont([(p, f) for _, p, f in entries], [])

    def _on_uninstall_from_user(self, entries):
        """批量取消安装（删除用户目录文件，被占用的重启后自动清理）。"""
        names = [os.path.basename(p) for _, _, p in entries]
        preview = "\n".join(f"· {n}" for n in names[:8]) + ("\n…" if len(names) > 8 else "")
        box = MessageBox(
            "取消安装",
            f"将移除 {len(entries)} 个字体（删除用户目录中的文件）：\n{preview}\n\n"
            "被占用的文件会在重启后自动清理。",
            self.window())
        box.yesButton.setText("取消安装")
        box.cancelButton.setText("保留")
        if not box.exec():
            return
        self._userfont_item_map = {p: it for it, f, p in entries}
        self._start_userfont([], [(f, p) for it, f, p in entries])

    def _start_userfont(self, to_install, to_uninstall) -> None:
        if self._register_worker is not None or self._userfont_worker is not None:
            return
        worker = UserFontWorker(to_install, to_uninstall, self)
        self._userfont_worker = worker
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self._set_busy(True)
        worker.progress.connect(self._on_userfont_progress)
        worker.finished_ok.connect(self._on_userfont_finished)
        worker.finished.connect(self._on_userfont_worker_done)
        worker.start()

    def _on_userfont_progress(self, done, total):
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
            self.status_label.setText(f"正在安装/取消安装字体 {done}/{total}")

    def _on_userfont_finished(self, results):
        for r in results:
            item = self._userfont_item_map.get(r["path"])
            if item is None:
                continue
            if r["kind"] == "install":
                if r["ok"]:
                    self._mark_installed_user(item, r["installed_path"])
                else:
                    InfoBar.error("安装失败", f"{os.path.basename(r['path'])}：{r['message']}",
                                  parent=self.window(), position=InfoBarPosition.TOP, duration=4000)
            elif r["ok"]:
                self._mark_uninstalled(item)
                if r["status"] == "locked":
                    InfoBar.warning("文件未删除", f"{os.path.basename(r['path'])} 的文件未能删除，"
                                    "但已取消注册，残留文件可手动清理。",
                                    parent=self.window(), position=InfoBarPosition.TOP, duration=5000)
        installed = [r for r in results if r["kind"] == "install" and r["ok"]]
        uninst = [r for r in results if r["kind"] == "uninstall" and r["ok"]]
        deferred = [r for r in uninst if r["status"] == "deferred"]
        parts = []
        if installed:
            parts.append(f"已安装 {len(installed)} 个字体")
        if uninst:
            parts.append(f"已取消 {len(uninst)} 个字体")
        if deferred:
            parts.append(f"{len(deferred)} 个文件重启后自动清理")
        if parts:
            InfoBar.info("字体安装已更新", "，".join(parts), parent=self.window(),
                         position=InfoBarPosition.TOP, duration=4000)
        self._update_status()

    def _on_userfont_worker_done(self):
        self.progress.setVisible(False)
        self._userfont_item_map = {}
        self._userfont_worker = None
        self._set_busy(self._register_worker is not None)

    def _item_display_name(self, item, fallback: str) -> str:
        """节点的展示名：Windows 标准字体名（win_name）优先，回退 family / 文件名。"""
        return (item.data(0, Qt.ItemDataRole.UserRole + 4)
                or item.data(0, Qt.ItemDataRole.UserRole + 1)
                or fallback)

    def _mark_installed_user(self, item, installed_path: str) -> None:
        """安装成功：节点置灰不可勾选；若正被会话注册则先注销（副本已可用）。"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path in self._registered:
            font_register.unregister_font(path)
            self._registered.discard(path)
        self.tree.blockSignals(True)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Unchecked)
        name = os.path.basename(path)
        item.setText(0, f"{name}（已安装到当前用户）")
        item.setForeground(0, QColor("#8a8a8a"))
        item.setToolTip(0, f"{self._item_display_name(item, name)} — 已安装到当前用户，可直接使用")
        item.setData(0, Qt.ItemDataRole.UserRole + 2, installed_path)
        self.tree.blockSignals(False)
        self._update_ancestors(item)

    def _mark_uninstalled(self, item) -> None:
        """取消安装：节点恢复可勾选（未勾选）。"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        self.tree.blockSignals(True)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Unchecked)
        name = os.path.basename(path)
        item.setText(0, name)
        item.setForeground(0, QBrush())
        item.setToolTip(0, self._item_display_name(item, name))
        item.setData(0, Qt.ItemDataRole.UserRole + 2, "")
        self.tree.blockSignals(False)
        self._update_ancestors(item)

    # ---------------------------------------------------------------- 底部预览

    def _on_current_item_changed(self, current, previous):
        """选中字体文件时用该字体渲染 4 行预览文字（含 TTC/OTC 整体与已安装到当前用户）。"""
        if current is None:
            self._clear_preview()
            return
        path = current.data(0, Qt.ItemDataRole.UserRole)
        installed_path = current.data(0, Qt.ItemDataRole.UserRole + 2)
        if not path or not current.data(0, Qt.ItemDataRole.UserRole + 6):
            self._clear_preview()  # 目录与 TTC face 子节点不预览
            return
        # 已安装到当前用户的字体读本地副本预览（更快，且库盘（如 RaiDrive）离线也能预览）
        self._preview_font(installed_path or path)

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
