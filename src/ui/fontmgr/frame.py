"""字体管理页：树形查看文件夹里的字体，勾选注册到 Windows（会话级），系统已装字体标记。

会话级注册：勾选即 AddFontResourceEx 加入系统字体表，全会话应用可枚举；取消即注销。
系统已装字体（注册表 Fonts 键 / Windows\\Fonts）在树里灰显标记，不提供勾选，避免误卸。
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QTreeWidgetItem,
    QVBoxLayout,
)
from qfluentwidgets import (
    CaptionLabel,
    FluentIcon as FIF,
    InfoBar,
    InfoBarPosition,
    PushButton,
    SubtitleLabel,
    TreeWidget,
    isDarkTheme,
    qconfig,
)

from config import option
from core import font_register
from ui.fontmgr.worker import ScanWorker


class FontManagerFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("FontManagerFrame")
        self._worker = None
        self._registered: set[str] = set()  # 本会话内由本工具注册过的字体路径

        self.title = SubtitleLabel("字体管理", self)
        self.hint = CaptionLabel(
            "勾选字体即注册到 Windows（当前会话有效，重启后失效）；取消勾选即注销。系统已安装的字体将被标记。", self)

        self.btn_add = PushButton(FIF.FOLDER_ADD, "选择文件夹", self)
        self.btn_add.clicked.connect(self._on_add_folder)
        self.btn_rescan = PushButton(FIF.SYNC, "重新扫描", self)
        self.btn_rescan.clicked.connect(self._on_rescan)

        self.tree = TreeWidget(self)
        self.tree.setColumnCount(1)
        self.tree.setHeaderLabels(["字体文件（勾选即注册到 Windows）"])
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.currentItemChanged.connect(self._on_current_item_changed)

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

        top = QHBoxLayout()
        top.addWidget(self.btn_add)
        top.addWidget(self.btn_rescan)
        top.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.hint)
        layout.addSpacing(8)
        layout.addLayout(top)
        layout.addWidget(self.tree, 1)
        layout.addWidget(self.preview_title)
        layout.addWidget(self.preview_label)
        layout.addWidget(self.status_label)
        self.setLayout(layout)

    # ---------------------------------------------------------------- 扫描

    def _on_add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择字体文件夹", option.import_dir.value)
        if not folder:
            return
        qconfig.set(option.import_dir, folder)
        existing = [
            self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
            for i in range(self.tree.topLevelItemCount())
        ]
        roots = [r for r in existing if r]
        if folder not in roots:
            roots.append(folder)  # 多个文件夹累加，不替换
        self._start_scan(roots)

    def _on_rescan(self):
        roots = [
            self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
            for i in range(self.tree.topLevelItemCount())
        ]
        roots = [r for r in roots if r]
        if roots:
            self._start_scan(roots)

    def _start_scan(self, roots: list[str]) -> None:
        if self._worker is not None:
            return
        self._worker = ScanWorker(roots, self)
        self.status_label.setText("扫描中…")
        self.btn_add.setEnabled(False)
        self.btn_rescan.setEnabled(False)
        self._worker.finished_ok.connect(self._on_scan_finished)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_scan_finished(self, tree, errors):
        self.tree.blockSignals(True)
        self.tree.clear()
        for node in tree:
            self.tree.addTopLevelItem(self._build_item(node))
        self.tree.blockSignals(False)
        self.status_label.setText(f"已加载 {len(tree)} 个文件夹，勾选字体即可注册到 Windows。")
        if errors:
            InfoBar.error("部分文件夹扫描失败", f"{len(errors)} 个文件夹：{errors[0][0]}",
                          parent=self.window(), position=InfoBarPosition.TOP, duration=4000)

    def _on_worker_finished(self):
        self.btn_add.setEnabled(True)
        self.btn_rescan.setEnabled(True)
        self._worker = None

    def _build_item(self, node: dict) -> QTreeWidgetItem:
        item = QTreeWidgetItem([node["name"]])
        item.setData(0, Qt.ItemDataRole.UserRole, node["path"])
        if node["is_font"] and not node["installed"]:
            # 可勾选字体叶子（QTreeWidgetItem 默认即含 ItemIsUserCheckable，这里显式保留）
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                0, Qt.CheckState.Checked if node["path"] in self._registered else Qt.CheckState.Unchecked)
            item.setToolTip(0, node["family"] or node["name"])
        else:
            # 目录 / 已装字体：清除默认勾选 flag，不提供勾选
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            if node["is_font"]:
                # 系统已装：灰显标记，避免误卸系统字体
                item.setText(0, f"{node['name']}（系统已安装）")
                item.setForeground(0, QColor("#8a8a8a"))
                item.setToolTip(0, f"{node['family'] or node['name']} — 已由系统安装，无需注册")
        for child in node.get("children", []):
            item.addChild(self._build_item(child))
        return item

    # ---------------------------------------------------------------- 注册/注销

    def _on_item_changed(self, item, column):
        if column != 0 or item.childCount() > 0:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            return
        if item.checkState(0) == Qt.CheckState.Checked:
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
        self._update_status()

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
