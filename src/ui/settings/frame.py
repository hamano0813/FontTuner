"""设置页：SettingCard 自然叠放。"""

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import QFileDialog, QFrame, QGridLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    ExpandGroupSettingCard,
    FluentIcon as FIF,
    InfoBar,
    InfoBarPosition,
    OptionsSettingCard,
    PlainTextEdit,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SettingCard,
    SpinBox,
    SwitchSettingCard,
    Theme,
    qconfig,
    setTheme,
)

from config import option
from core import autostart, mpv_plugin
from ui.settings.update_card import UpdateCard


class PreviewTextCard(ExpandGroupSettingCard):
    """预览设置卡（下拉式）：头部左侧是预览字号 spinbox，展开显示预览文字编辑框。

    编辑页与字体管理页的预览共用这段文字（一行一种语言），字号/文字改动经
    option 的 valueChanged 即时重绘。
    """

    def __init__(self, parent=None):
        super().__init__(
            FIF.EDIT, "预览文字",
            "字体编辑页与字体管理页的预览共用这段文字。",
            parent,
        )
        # 头部：下拉按钮左侧的预览字号 spinbox
        self.size_spin = SpinBox(self)
        self.size_spin.setRange(8, 72)
        self.size_spin.setValue(option.preview_font_size.value)
        self.size_spin.setToolTip("预览字号（pt）")
        self.size_spin.valueChanged.connect(self._on_size_changed)
        self.addWidget(self.size_spin)

        # 展开区：预览文字编辑框
        self.edit = PlainTextEdit(self)
        self.edit.setPlainText(option.preview_sample.value)
        self.edit.setPlaceholderText("输入预览文字，可多行换行…")
        self.edit.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.edit.setFixedHeight(120)
        self.edit.setMinimumWidth(300)

        # 防抖持久化：停止输入 600ms 后写回配置
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(600)
        self._save_timer.timeout.connect(self._persist_sample)
        self.edit.textChanged.connect(lambda: self._save_timer.start())

        self.addGroupWidget(self.edit)

    def _persist_sample(self) -> None:
        qconfig.set(option.preview_sample, self.edit.toPlainText())

    def _on_size_changed(self, value: int) -> None:
        qconfig.set(option.preview_font_size, value)


class MpvPluginCard(ExpandGroupSettingCard):
    """MPV 插件设置卡：硬链接目录 + MPV 脚本目录 + 写入脚本。"""

    def __init__(self, parent=None):
        super().__init__(
            FIF.VIDEO, "MPV 插件",
            "联动 MPV：自动为当前字幕挂载所需字体（写入 Lua 脚本 + 硬链接目录）",
            parent,
        )
        self.viewLayout.setContentsMargins(0, 0, 0, 0)
        self.viewLayout.setSpacing(0)

        self.link_btn = PushButton("选择文件夹", self)
        self.link_btn.setFixedWidth(135)
        self.link_btn.clicked.connect(self._pick_link_dir)
        self.link_group = self.addGroup(
            FIF.FOLDER, "设置硬链接目录",
            self._content(option.mpv_link_dir.value), self.link_btn)

        self.scripts_btn = PushButton("选择文件夹", self)
        self.scripts_btn.setFixedWidth(135)
        self.scripts_btn.clicked.connect(self._pick_scripts_dir)
        self.scripts_group = self.addGroup(
            FIF.CODE, "设置 MPV 脚本目录",
            self._content(option.mpv_scripts_dir.value), self.scripts_btn)

        self.write_btn = PrimaryPushButton("写入脚本", self)
        self.write_btn.setFixedWidth(135)
        self.write_btn.clicked.connect(self._on_write_script)
        self.addGroup(
            FIF.SAVE, "写入脚本",
            "生成联动 Lua 脚本到 MPV 脚本目录（自动嵌入当前字体缓存路径）",
            self.write_btn)

    @staticmethod
    def _content(path: str) -> str:
        return path or "未设置"

    def _pick_link_dir(self):
        dir_ = QFileDialog.getExistingDirectory(
            self.window(), "选择硬链接目录", option.mpv_link_dir.value or "")
        if dir_:
            qconfig.set(option.mpv_link_dir, dir_)
            self.link_group.setContent(dir_)

    def _pick_scripts_dir(self):
        dir_ = QFileDialog.getExistingDirectory(
            self.window(), "选择 MPV 脚本目录", option.mpv_scripts_dir.value or "")
        if dir_:
            qconfig.set(option.mpv_scripts_dir, dir_)
            self.scripts_group.setContent(dir_)

    def _on_write_script(self):
        ok, msg_ = mpv_plugin.write_script(
            option.mpv_scripts_dir.value, option.mpv_link_dir.value)
        if ok:
            InfoBar.success("已写入脚本", msg_, parent=self.window(),
                            position=InfoBarPosition.TOP, duration=4000)
        else:
            InfoBar.error("写入脚本失败", msg_, parent=self.window(),
                          position=InfoBarPosition.TOP, duration=5000)


class SettingsFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("SettingsFrame")
        self.sub_frame = QFrame(self)

        # ===== 启动 =====
        self.autostart_card = SwitchSettingCard(
            FIF.POWER_BUTTON, "开机自动启动", "开机时自动启动拾字 FontTuner", parent=self,
        )
        self.autostart_card.setChecked(autostart.is_enabled())
        self.autostart_card.checkedChanged.connect(self._on_autostart_toggled)

        self.auto_restore_card = SwitchSettingCard(
            FIF.HISTORY, "自动恢复选中",
            "启动后自动恢复字体管理页保存的选中字体（配合开机自启，重启后自动重新注册）",
            configItem=option.fontmgr_auto_restore, parent=self,
        )

        # ===== 界面设置 =====
        self.theme_card = OptionsSettingCard(
            option.themeMode, FIF.PALETTE, "主题模式", "更改界面显示颜色",
            texts=["浅色", "深色", "跟随系统设置"],
        )
        # 用 QConfig 的 themeChanged（在 qconfig.theme 解析完成后触发），
        # 而非 themeMode.valueChanged（在解析前触发，setTheme 会读到旧主题）
        option.themeChanged.connect(self.theme_changed)

        # ===== 预览文字 =====
        self.preview_text_card = PreviewTextCard(self)

        # ===== MPV 插件 =====
        self.mpv_plugin_card = MpvPluginCard(self)

        # ===== 关于 =====
        self.about_card = SettingCard(
            FIF.INFO, "拾字 FontTuner",
            "批量编辑字体元数据（字重/字宽/斜体、多语言名称、版权/许可/厂商等）；TTC/OTC 集合解包与打包；"
            "注册字体到 Windows；并提供信息模板、跨语言翻译与多语言预览。支持 .ttf/.otf/.ttc/.otc。",
            self,
        )

        # ===== 版权信息（含检查更新）=====
        self.update_card = UpdateCard(self)

        # 无分组标题、无说明 label：SettingCard 自然叠放
        sub_layout = QVBoxLayout()
        sub_layout.addWidget(self.autostart_card)
        sub_layout.addWidget(self.auto_restore_card)
        sub_layout.addWidget(self.theme_card)
        sub_layout.addWidget(self.preview_text_card)
        sub_layout.addWidget(self.mpv_plugin_card)
        sub_layout.addWidget(self.about_card)
        sub_layout.addWidget(self.update_card)
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

    def _on_autostart_toggled(self, checked: bool) -> None:
        """开机自启开关：写入/删除 HKCU Run 键（指向引导 exe）。

        开发态没有引导 exe（FontTuner.exe），enable 失败 → 回弹开关并提示。
        注意：回弹用 setChecked(False) 会再触发 checkedChanged(False) → disable()，
        幂等无害，不会死循环。
        """
        if checked:
            if not autostart.enable():
                self.autostart_card.setChecked(False)
                InfoBar.error(
                    title="开机自动启动",
                    content="仅安装版支持开机自启（未找到引导程序 FontTuner.exe）。",
                    parent=self.window(), position=InfoBarPosition.TOP, duration=4000,
                )
        else:
            if not autostart.disable():
                InfoBar.error(
                    title="开机自动启动",
                    content="无法写入注册表，请检查系统权限。",
                    parent=self.window(), position=InfoBarPosition.TOP, duration=4000,
                )

    def theme_changed(self, theme: Theme) -> None:
        """主题切换：应用主题并刷新所有控件的自定义样式（VAS 模式）。"""
        setTheme(theme)
        self.window().reset_style()
