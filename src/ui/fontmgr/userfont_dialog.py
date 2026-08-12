"""当前用户已安装字体管理对话框：读 HKCU 注册表列出所有「已安装到当前用户」的字体。

不依赖字体库树——库文件丢失、目录列表丢失、本地化显示名与英文家族名不匹配时，
这里仍能逐个取消安装，覆盖孤儿注册表条目（文件已缺失）的清理。
卸载按注册表指向的路径精确匹配，不依赖家族名。
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QTableWidgetItem,
)
from qfluentwidgets import (
    BodyLabel,
    MessageBoxBase,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
    TableWidget,
)
from qfluentwidgets.common.smooth_scroll import SmoothMode

from core import userfont


class UserFontManageDialog(MessageBoxBase):
    """列出当前用户已安装字体，逐个取消安装（含文件缺失标记）。

    关闭后经 removed 取本次卸载成功的 (family, path) 列表，供调用方刷新库树。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.removed: list[tuple[str, str]] = []  # 卸载成功记录 (family, path)

        self.title_label = SubtitleLabel("当前用户已安装字体", self)
        self.hint = BodyLabel(
            "直接读取注册表，与字体库无关。文件缺失的条目是孤儿登记，同样可一并清理。", self)

        self.table = TableWidget(self)
        # 禁用平滑滚动（NO_SMOOTH），行数多时滚动更跟手
        self.table.scrollDelagate.verticalSmoothScroll.setSmoothMode(SmoothMode.NO_SMOOTH)
        self.table.scrollDelagate.horizonSmoothScroll.setSmoothMode(SmoothMode.NO_SMOOTH)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["字体名", "文件路径", "状态", "操作"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setWordWrap(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 260)
        header.resizeSection(2, 96)
        header.resizeSection(3, 110)

        self._rows: list[dict] = []  # 每行 {value_name, family, path, exists, button}

        # 底部：统计 + 一键清理缺失项
        self._footer = BodyLabel("", self)
        self.clean_missing_btn = PushButton("清理缺失项", self)
        self.clean_missing_btn.setToolTip("卸载所有文件已缺失的孤儿注册表条目")
        self.clean_missing_btn.clicked.connect(self._clean_all_missing)

        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addWidget(self.hint)
        self.viewLayout.addWidget(self.table)
        self.viewLayout.addSpacing(4)
        footer_row = QHBoxLayout()
        footer_row.addWidget(self._footer, 1)
        footer_row.addWidget(self.clean_missing_btn)
        self.viewLayout.addLayout(footer_row)
        self.widget.setMinimumSize(820, 640)
        self.yesButton.hide()
        self.cancelButton.setText("关闭")

        self._refresh()

    # ---------------------------------------------------------------- 表格

    def _refresh(self) -> None:
        """从注册表重建表格（每次打开/清理后刷新最新状态）。"""
        entries = userfont.list_user_fonts()
        self.table.setRowCount(len(entries))
        self._rows = []
        for row, entry in enumerate(entries):
            exists = os.path.isfile(entry["path"])
            fam_item = QTableWidgetItem(entry["family"])
            fam_item.setToolTip(entry["value_name"])
            path_item = QTableWidgetItem(entry["path"])
            path_item.setToolTip(entry["path"])
            state_item = QTableWidgetItem("已就绪" if exists else "文件缺失")
            state_item.setForeground(QColor("#2aa198") if exists else QColor("#e05757"))
            btn = PrimaryPushButton("取消安装", self.table)
            btn.setFixedWidth(96)
            btn.clicked.connect(lambda _, r=row: self._uninstall_row(r))
            self.table.setItem(row, 0, fam_item)
            self.table.setItem(row, 1, path_item)
            self.table.setItem(row, 2, state_item)
            self.table.setCellWidget(row, 3, btn)
            self._rows.append({**entry, "exists": exists, "button": btn})
        missing = sum(1 for r in self._rows if not r["exists"])
        self._footer.setText(f"共 {len(self._rows)} 项，其中 {missing} 项文件缺失（孤儿条目）。")
        self.clean_missing_btn.setVisible(missing > 0)

    def _uninstall_row(self, row: int) -> None:
        """取消安装指定行：按注册表指向路径精确卸载，成功则标记该行并记录。"""
        entry = self._rows[row]
        btn = entry["button"]
        btn.setEnabled(False)
        btn.setText("卸载中…")
        btn.repaint()
        ok, status, detail = userfont.uninstall_user_font_by_path(entry["path"])
        if ok:
            self.removed.append((entry["family"], entry["path"]))
            btn.setText("已卸载")
            btn.setDisabled(True)
            # 行置灰表示已处理
            for col in range(3):
                item = self.table.item(row, col)
                if item is not None:
                    item.setForeground(QColor("#9a9a9a"))
            # 状态列同步
            state_item = self.table.item(row, 2)
            if state_item is not None:
                state_item.setText("已卸载")
        else:
            btn.setText("失败")
            btn.setEnabled(True)
            self._footer.setText(f"卸载失败：{detail}")
        if ok:
            self._footer.setText(f"已卸载 {len(self.removed)} 项。")

    def _clean_all_missing(self) -> None:
        """一键卸载所有文件缺失的孤儿条目（自顶向下循环，直到本轮无缺失）。"""
        done = 0
        # 注意：卸载成功后行状态标记为已处理，exists 语义保留，故按初始 missing 列表驱动
        for row in range(len(self._rows) - 1, -1, -1):
            entry = self._rows[row]
            if entry["exists"]:
                continue
            btn = entry["button"]
            btn.setEnabled(False)
            btn.setText("卸载中…")
            btn.repaint()
            ok, status, detail = userfont.uninstall_user_font_by_path(entry["path"])
            if ok:
                self.removed.append((entry["family"], entry["path"]))
                done += 1
                btn.setText("已卸载")
                btn.setDisabled(True)
                for col in range(3):
                    item = self.table.item(row, col)
                    if item is not None:
                        item.setForeground(QColor("#9a9a9a"))
                state_item = self.table.item(row, 2)
                if state_item is not None:
                    state_item.setText("已卸载")
        self._footer.setText(f"已清理 {done} 项缺失条目。" if done else "没有缺失项。")
        self.clean_missing_btn.setVisible(False)
