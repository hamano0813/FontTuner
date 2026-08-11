"""基于 QConfig 的全局配置，持久化到 config.json（开发态在仓库根，打包态在 %APPDATA%\\FontTuner）。

themeMode / themeColor 由 QConfig 基类提供；这里覆盖 themeMode 默认值为「跟随系统」。
"""

from qfluentwidgets import (
    BoolValidator,
    ConfigItem,
    EnumSerializer,
    FolderListValidator,
    FolderValidator,
    OptionsConfigItem,
    OptionsValidator,
    QConfig,
    RangeValidator,
    Theme,
    qconfig,
)

from core.paths import user_data_dir

CONFIG_PATH = user_data_dir() / "config.json"


class Option(QConfig):
    # 覆盖基类默认（LIGHT）为「跟随系统」；EnumSerializer 使 Theme 枚举可序列化
    themeMode = OptionsConfigItem(
        "QFluentWidgets", "ThemeMode", Theme.AUTO,
        OptionsValidator([Theme.LIGHT, Theme.DARK, Theme.AUTO]),
        EnumSerializer(Theme),
    )

    # 上次导入字体的目录，供文件对话框记忆
    import_dir = ConfigItem("OPTION", "IMPORT_DIR", "", FolderValidator())

    # 解包/打包页的输出目录，供文件对话框记忆
    package_out_dir = ConfigItem("OPTION", "PACKAGE_OUT_DIR", "", FolderValidator())

    # 字体管理页扫描的字体库目录列表（持久化，重启后自动重新扫描）
    fontmgr_folders = ConfigItem("OPTION", "FONTMGR_FOLDERS", [], FolderListValidator())

    # 字体管理页「保存选中」的字体路径列表（供「恢复选中」与启动自动恢复使用）
    fontmgr_saved_selection = ConfigItem("OPTION", "FONTMGR_SAVED_SELECTION", [])

    # 启动后自动恢复字体管理页保存的选中字体（配合开机自启，重启后自动重新注册）
    fontmgr_auto_restore = ConfigItem(
        "OPTION", "FONTMGR_AUTO_RESTORE", False, BoolValidator()
    )

    # 字体预览的样例文字（PlainTextEdit 内容），重启后保留；一行一个语言
    preview_sample = ConfigItem(
        "OPTION", "PREVIEW_SAMPLE",
        "这是简体中文的测试文字，用来测试字体是否支持正常显示\n"
        "這是繁體中文的測試文字，用來測試字體是否支援正常顯示\n"
        "これは日本語のテストテキストです。フォントが正常に表示されるかテストします\n"
        "English test: ABC abc 0123",
    )

    # 字体预览的字号（点），由预览面板 spinbox 调节
    preview_font_size = ConfigItem("OPTION", "PREVIEW_FONT_SIZE", 24, RangeValidator(8, 72))

    # MPV 联动：字体硬链接目录（与字体库同盘），及 mpv/Jellyfin 的 scripts 目录
    mpv_link_dir = ConfigItem("OPTION", "MPV_LINK_DIR", "", FolderValidator())
    mpv_scripts_dir = ConfigItem("OPTION", "MPV_SCRIPTS_DIR", "", FolderValidator())


option = Option()
qconfig.load(str(CONFIG_PATH), option)
