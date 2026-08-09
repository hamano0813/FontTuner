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

    # 字体预览的样例文字（PlainTextEdit 内容），重启后保留；一行一个语言
    preview_sample = ConfigItem(
        "OPTION", "PREVIEW_SAMPLE",
        "这是简体中文的测试文字，用来测试字体是否支持正常显示\n"
        "這是繁體中文的測試文字，用來測試字體是否支援正常顯示\n"
        "これは日本語のテストテキストです。フォントが正常に表示されるかテストします\n"
        "English test: ABC abc 0123",
    )

    # 字体文件重命名模板，{字段_xx} 按字体动态替换（xx=sc/tc/jp/en）
    rename_template = ConfigItem(
        "OPTION", "RENAME_TEMPLATE", "{preferred_family_sc} {weight_sc} {width_sc} {version_sc}"
    )


option = Option()
qconfig.load(str(CONFIG_PATH), option)
