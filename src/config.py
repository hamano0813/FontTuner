"""基于 QConfig 的全局配置，持久化到仓库根 config.json。

themeMode / themeColor 由 QConfig 基类提供；这里覆盖 themeMode 默认值为「跟随系统」。
"""

from pathlib import Path

from qfluentwidgets import (
    ConfigItem,
    EnumSerializer,
    FolderValidator,
    OptionsConfigItem,
    OptionsValidator,
    QConfig,
    Theme,
    qconfig,
)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


class Option(QConfig):
    # 覆盖基类默认（LIGHT）为「跟随系统」；EnumSerializer 使 Theme 枚举可序列化
    themeMode = OptionsConfigItem(
        "QFluentWidgets", "ThemeMode", Theme.AUTO,
        OptionsValidator([Theme.LIGHT, Theme.DARK, Theme.AUTO]),
        EnumSerializer(Theme),
    )

    # 上次导入字体的目录，供文件对话框记忆
    import_dir = ConfigItem("OPTION", "IMPORT_DIR", "", FolderValidator())


option = Option()
qconfig.load(str(CONFIG_PATH), option)
