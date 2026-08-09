"""设置页：SettingCard 自然叠放；重命名模板用 ExpandGroupSettingCard 手风琴卡。"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import QFrame, QGridLayout, QSpacerItem, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    ExpandGroupSettingCard,
    FluentIcon as FIF,
    LineEdit,
    OptionsSettingCard,
    PlainTextEdit,
    ScrollArea,
    SettingCard,
    Theme,
    qconfig,
    setTheme,
)

from config import option
from core.font_service import RENAME_PLACEHOLDERS


class RenameTemplateCard(ExpandGroupSettingCard):
    """手风琴重命名模板卡：头部 LineEdit 记录模板（在下拉按钮左侧），
    展开显示 {占位符} ↔ 名称 的映射关系表。"""

    def __init__(self, parent=None):
        super().__init__(FIF.TAG, "重命名模板", "字体文件重命名格式", parent)
        self.configItem = option.rename_template

        self.lineEdit = LineEdit(self)
        self.lineEdit.setClearButtonEnabled(True)
        self.lineEdit.setFixedWidth(720)
        self.lineEdit.setText(qconfig.get(self.configItem))
        self.lineEdit.editingFinished.connect(self._onEditingFinished)
        self.configItem.valueChanged.connect(self.setValue)
        self.addWidget(self.lineEdit)  # HeaderSettingCard.addWidget 插到下拉按钮左侧

        self._build_mapping()

    def setValue(self, value):
        """配置被外部修改时同步到输入框。"""
        if self.lineEdit.text() != value:
            self.lineEdit.setText(value)

    def _onEditingFinished(self):
        qconfig.set(self.configItem, self.lineEdit.text().strip())

    def _build_mapping(self):
        """展开区：名称 ↔ {占位符} 映射表 + 语言后缀说明，全部用 CaptionLabel。"""
        table = QWidget(self.view)
        grid = QGridLayout(table)
        grid.setContentsMargins(24, 16, 24, 16)
        grid.setHorizontalSpacing(8)    # 两列靠近一点
        grid.setVerticalSpacing(6)
        # 网格按内容宽度固定，禁止列拉伸把占位符推到中间
        grid.setSizeConstraint(QGridLayout.SizeConstraint.SetFixedSize)
        for row, (cn, ph) in enumerate(RENAME_PLACEHOLDERS):
            grid.addWidget(CaptionLabel(cn), row, 0)   # 中文名居左
            grid.addWidget(CaptionLabel(ph), row, 1)
        grid.addWidget(
            CaptionLabel("xx 可替换为四种语言：sc/tc/jp/en（简/繁/日/英）"),
            len(RENAME_PLACEHOLDERS), 0, 1, 2,
        )
        self.addGroupWidget(table)


class PreviewTextCard(SettingCard):
    """预览文字设置卡：右侧多行编辑框，绑定 option.preview_sample。

    编辑页与字体管理页的预览共用这段文字（一行一种语言），改动经 valueChanged 即时重绘。
    """

    def __init__(self, parent=None):
        super().__init__(
            FIF.EDIT, "预览文字",
            "字体编辑页与字体管理页的预览共用这段文字，一行一种语言（简/繁/日/英）。",
            parent,
        )
        # 放开 SettingCard 默认固定高度，让卡片随编辑区增高
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)

        self.edit = PlainTextEdit(self)
        self.edit.setPlainText(option.preview_sample.value)
        self.edit.setPlaceholderText("一行一种语言（简/繁/日/英）…")
        self.edit.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.edit.setMaximumHeight(120)

        # 防抖持久化：停止输入 600ms 后写回配置
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(600)
        self._save_timer.timeout.connect(self._persist)
        self.edit.textChanged.connect(lambda: self._save_timer.start())

        # 移除父 hBox 末尾的 stretch，让编辑区独占剩余宽度
        for i in range(self.hBoxLayout.count()):
            if isinstance(self.hBoxLayout.itemAt(i), QSpacerItem):
                self.hBoxLayout.removeItem(self.hBoxLayout.itemAt(i))
                break
        self.hBoxLayout.addWidget(self.edit, 1, Qt.AlignmentFlag.AlignVCenter)

    def _persist(self) -> None:
        qconfig.set(option.preview_sample, self.edit.toPlainText())


class SettingsFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("SettingsFrame")
        self.sub_frame = QFrame(self)

        # ===== 界面设置 =====
        self.theme_card = OptionsSettingCard(
            option.themeMode, FIF.PALETTE, "主题模式", "更改界面显示颜色",
            texts=["浅色", "深色", "跟随系统设置"],
        )
        # 用 QConfig 的 themeChanged（在 qconfig.theme 解析完成后触发），
        # 而非 themeMode.valueChanged（在解析前触发，setTheme 会读到旧主题）
        option.themeChanged.connect(self.theme_changed)

        # ===== 重命名模板（手风琴卡）=====
        self.rename_card = RenameTemplateCard(self)

        # ===== 预览文字 =====
        self.preview_text_card = PreviewTextCard(self)

        # ===== 关于 =====
        self.about_card = SettingCard(
            FIF.INFO, "FontTuner",
            "批量编辑字体元数据：字重/字宽/斜体、四语种名称及版权许可厂商记录。支持 .ttf/.otf/.ttc/.otc。",
            self,
        )
        self.copyright_card = SettingCard(
            FIF.COPY, "版权信息", "© 2026 FontTuner · 保留所有权利", self,
        )

        # 无分组标题、无说明 label：SettingCard 自然叠放
        sub_layout = QVBoxLayout()
        sub_layout.addWidget(self.theme_card)
        sub_layout.addWidget(self.rename_card)
        sub_layout.addWidget(self.preview_text_card)
        sub_layout.addWidget(self.about_card)
        sub_layout.addWidget(self.copyright_card)
        sub_layout.addStretch()
        self.sub_frame.setLayout(sub_layout)

        self.scroll_area = ScrollArea(self)
        self.scroll_area.setWidget(self.sub_frame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.enableTransparentBackground()

        layout = QVBoxLayout(self)
        layout.addWidget(self.scroll_area)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def theme_changed(self, theme: Theme) -> None:
        """主题切换：应用主题并刷新所有控件的自定义样式（VAS 模式）。"""
        setTheme(theme)
        self.window().reset_style()
