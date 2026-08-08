"""设置页：VAS 式卡片布局（ScrollArea + SettingCardGroup），主题持久化 + 版权信息。"""

from PySide6.QtWidgets import QFrame, QVBoxLayout
from qfluentwidgets import (
    FluentIcon as FIF,
    OptionsSettingCard,
    ScrollArea,
    SettingCard,
    SettingCardGroup,
    Theme,
    setTheme,
)

from config import option


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
        option.themeMode.valueChanged.connect(self._on_theme_changed)

        # ===== 关于 =====
        self.about_card = SettingCard(
            FIF.INFO, "FontTuner",
            "批量编辑字体元数据：字重/字宽/斜体、四语种名称及版权许可厂商记录。支持 .ttf/.otf/.ttc/.otc。",
            self,
        )
        self.copyright_card = SettingCard(
            FIF.COPY, "版权信息", "© 2026 FontTuner · 保留所有权利", self,
        )

        self.ui_group = self.create_group("界面设置", [self.theme_card])
        self.about_group = self.create_group("关于", [self.about_card, self.copyright_card])

        sub_layout = QVBoxLayout()
        sub_layout.addWidget(self.ui_group)
        sub_layout.addWidget(self.about_group)
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

    def create_group(self, title: str, widgets: list) -> SettingCardGroup:
        group = SettingCardGroup(title, self)
        for widget in widgets:
            group.addSettingCard(widget)
        return group

    def _on_theme_changed(self, theme: Theme) -> None:
        setTheme(theme)
