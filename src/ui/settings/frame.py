"""设置页：GroupHeaderCardWidget 上下分组卡片，主题 + 重命名模板 + 关于。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    FluentIcon as FIF,
    GroupHeaderCardWidget,
    LineEdit,
    OptionsSettingCard,
    ScrollArea,
    SettingCard,
    Theme,
    qconfig,
    setTheme,
)

from config import option
from core.font_service import rename_placeholder_help


class TextSettingCard(SettingCard):
    """文本配置卡片：绑定 ConfigItem，编辑结束写回配置。

    按 qfw 标准模式（同 ComboBoxSettingCard）：构造时从配置取值、
    编辑结束 qconfig.set、响应 valueChanged 双向同步。
    """

    def __init__(self, configItem, icon, title, content=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.configItem = configItem
        self.lineEdit = LineEdit(self)
        self.lineEdit.setClearButtonEnabled(True)
        self.lineEdit.setFixedWidth(320)
        self.hBoxLayout.addWidget(self.lineEdit, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.lineEdit.setText(qconfig.get(configItem))
        self.lineEdit.editingFinished.connect(self._onEditingFinished)
        configItem.valueChanged.connect(self.setValue)

    def setValue(self, value):
        """配置被外部修改时同步到输入框。"""
        if self.lineEdit.text() != value:
            self.lineEdit.setText(value)

    def _onEditingFinished(self):
        qconfig.set(self.configItem, self.lineEdit.text().strip())


class SettingsFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("SettingsFrame")

        # ===== 主题（OptionsSettingCard 管理 themeMode）=====
        self.theme_card = OptionsSettingCard(
            option.themeMode, FIF.PALETTE, "主题模式", "更改界面显示颜色",
            texts=["浅色", "深色", "跟随系统设置"],
        )
        # 用 QConfig 的 themeChanged（在 qconfig.theme 解析完成后触发），
        # 而非 themeMode.valueChanged（在解析前触发，setTheme 会读到旧主题）
        option.themeChanged.connect(self.theme_changed)

        # ===== 重命名模板（TextSettingCard 管理 rename_template）=====
        self.rename_card = TextSettingCard(
            option.rename_template, FIF.TAG, "重命名模板", "字体文件重命名格式，可改可用变量", self)
        self.rename_hint = CaptionLabel(
            "重命名模板变量（中文列名 - {占位符}）：\n"
            + rename_placeholder_help()
            + "\n\n变量为空时替换为空并自动合并多余空格。", self,
        )

        # ===== 关于 =====
        self.about_card = SettingCard(
            FIF.INFO, "FontTuner",
            "批量编辑字体元数据：字重/字宽/斜体、四语种名称及版权许可厂商记录。支持 .ttf/.otf/.ttc/.otc。",
            self,
        )
        self.copyright_card = SettingCard(
            FIF.COPY, "版权信息", "© 2026 FontTuner · 保留所有权利", self,
        )

        # ===== 设置主卡片：一个 GroupHeaderCardWidget，三个上下分组 =====
        self.settings_card = GroupHeaderCardWidget("设置", self)
        self.settings_card.setBorderRadius(8)

        self.ui_group = self.settings_card.addGroup(FIF.SETTING, "界面设置", "主题外观", QWidget(self))
        self.ui_group.vBoxLayout.addWidget(self.theme_card)

        self.file_group = self.settings_card.addGroup(FIF.FOLDER, "文件操作", "重命名模板", QWidget(self))
        self.file_group.vBoxLayout.addWidget(self.rename_card)
        self.file_group.vBoxLayout.addWidget(self.rename_hint)

        self.about_group = self.settings_card.addGroup(FIF.INFO, "关于", "版权信息", QWidget(self))
        self.about_group.vBoxLayout.addWidget(self.about_card)
        self.about_group.vBoxLayout.addWidget(self.copyright_card)

        self.scroll_area = ScrollArea(self)
        self.scroll_area.setWidget(self.settings_card)
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
