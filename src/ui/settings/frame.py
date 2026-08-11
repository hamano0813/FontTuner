"""设置页：SettingCard 自然叠放。"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import QFileDialog, QFrame, QSpacerItem, QVBoxLayout, QWidget
from qfluentwidgets import (
    ExpandGroupSettingCard,
    FluentIcon as FIF,
    FolderListSettingCard,
    HyperlinkCard,
    InfoBar,
    InfoBarPosition,
    OptionsSettingCard,
    PlainTextEdit,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SettingCardGroup,
    SpinBox,
    SwitchButton,
    SwitchSettingCard,
    Theme,
    qconfig,
    setFont,
    setTheme,
)

from config import option
from core import autostart, mpv_plugin
from ui.settings.update_card import UpdateCard


class ZhSwitchSettingCard(SwitchSettingCard):
    """开关文本汉化的设置卡：覆盖基类 setValue 的 On/Off 硬编码。

    基类每次切换都会 switchButton.setText(tr('On')/tr('Off'))，把自定义文本
    冲掉；这里改为只 setChecked（内部 _updateText 会按 setOnText/setOffText
    刷新），使「开启/关闭」在切换后保持不变。
    """

    def setValue(self, isChecked: bool) -> None:
        if self.configItem:
            qconfig.set(self.configItem, isChecked)
        self.switchButton.setChecked(isChecked)


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
        self.size_spin.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)  # 输入框禁用右键菜单
        self.size_spin.setRange(8, 72)
        self.size_spin.setValue(option.preview_font_size.value)
        self.size_spin.setToolTip("预览字号（pt）")
        self.size_spin.valueChanged.connect(self._on_size_changed)
        self.addWidget(self.size_spin)

        # 展开区：预览文字编辑框
        self.edit = PlainTextEdit(self)
        # 纯展示输入框，禁用右键菜单，避免误触发复制/粘贴等编辑操作
        self.edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
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


class MpvScriptsCard(FolderListSettingCard):
    """MPV 脚本目录列表卡：管理各 MPV / Jellyfin 副本的 scripts 目录。

    删除目录不做确认（目录本身不会被删除），即时生效。
    """

    def __init__(self, parent=None):
        super().__init__(
            option.mpv_scripts_dirs, "MPV 脚本目录",
            "各 MPV / Jellyfin 副本的 scripts 目录，写入脚本时全部生成",
            directory=(option.mpv_scripts_dirs.value or [""])[0],
            parent=parent,
        )
        self.addFolderButton.setText("添加文件夹")

    def _FolderListSettingCard__showConfirmDialog(self, item):
        # 覆盖 qfw 的删除确认框：不弹框，直接移除（对应 qfw 内部 __showConfirmDialog）
        self._FolderListSettingCard__removeFolder(item)


class MpvPluginCard(ExpandGroupSettingCard):
    """插件设置卡：硬链接目录 + 日志开关 + 写入脚本（脚本目录由 MpvScriptsCard 管理）。"""

    def __init__(self, parent=None):
        super().__init__(
            FIF.VIDEO, "插件设置",
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

        # 日志开关：关闭后脚本不输出任何日志（mpv 控制台与同目录 sub-font-tuner.log）
        self.log_switch = SwitchButton(self)
        self.log_switch.setChecked(option.mpv_log_enable.value)
        self.log_switch.setOnText("开启")
        self.log_switch.setOffText("关闭")
        self.log_switch.setFixedWidth(135)
        self.log_switch.checkedChanged.connect(self._on_log_toggled)
        self.addGroup(
            FIF.BOOK_SHELF, "日志开关",
            "控制联动 Lua 脚本是否输出日志（开启时写入脚本同目录 sub-font-tuner.log）",
            self.log_switch)

        self.write_btn = PrimaryPushButton("写入脚本", self)
        self.write_btn.setFixedWidth(135)
        self.write_btn.clicked.connect(self._on_write_script)
        self.addGroup(
            FIF.SAVE, "写入脚本",
            "生成联动 Lua 脚本到全部 MPV 脚本目录（自动嵌入当前字体缓存路径）",
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

    def _on_log_toggled(self, checked: bool) -> None:
        """日志开关：持久化配置；目录已配置时立即重写全部脚本，让开关即时生效。"""
        qconfig.set(option.mpv_log_enable, checked)
        if option.mpv_scripts_dirs.value and option.mpv_link_dir.value:
            ok, msg_ = mpv_plugin.write_script(
                option.mpv_scripts_dirs.value, option.mpv_link_dir.value,
                log_enable=checked)
            if ok:
                InfoBar.success("已更新脚本", msg_, parent=self.window(),
                                position=InfoBarPosition.TOP, duration=3000)
            else:
                InfoBar.error("更新脚本失败", msg_, parent=self.window(),
                              position=InfoBarPosition.TOP, duration=5000)

    def _on_write_script(self):
        ok, msg_ = mpv_plugin.write_script(
            option.mpv_scripts_dirs.value, option.mpv_link_dir.value,
            log_enable=option.mpv_log_enable.value)
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
        self.close_to_tray_card = ZhSwitchSettingCard(
            FIF.HIDE, "关闭到系统托盘",
            "关闭窗口时最小化到系统托盘，右键托盘图标可退出程序",
            configItem=option.close_to_tray, parent=self,
        )
        self.close_to_tray_card.switchButton.setOnText("开启")
        self.close_to_tray_card.switchButton.setOffText("关闭")

        self.autostart_card = ZhSwitchSettingCard(
            FIF.POWER_BUTTON, "开机自动启动", "开机时自动启动拾字 FontTuner", parent=self,
        )
        self.autostart_card.switchButton.setOnText("开启")
        self.autostart_card.switchButton.setOffText("关闭")
        self.autostart_card.setChecked(autostart.is_enabled())
        self.autostart_card.checkedChanged.connect(self._on_autostart_toggled)

        self.auto_restore_card = ZhSwitchSettingCard(
            FIF.HISTORY, "自动恢复选中",
            "启动后自动恢复字体管理页保存的选中字体（配合开机自启，重启后自动重新注册）",
            configItem=option.fontmgr_auto_restore, parent=self,
        )
        self.auto_restore_card.switchButton.setOnText("开启")
        self.auto_restore_card.switchButton.setOffText("关闭")

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
        self.mpv_scripts_card = MpvScriptsCard(self)  # 多 MPV 副本 scripts 目录列表

        # ===== 关于 =====
        self.about_card = HyperlinkCard(
            "https://github.com/hamano0813/FontTuner", "GitHub 项目页", FIF.INFO,
            "拾字 FontTuner",
            "批量编辑字体元数据（字重/字宽/斜体、多语言名称、版权/许可/厂商等）；TTC/OTC 集合解包与打包；"
            "注册字体到 Windows；并提供信息模板、跨语言翻译与多语言预览。支持 .ttf/.otf/.ttc/.otc。",
            self,
        )

        # ===== 版权信息（含检查更新）=====
        self.update_card = UpdateCard(self)

        # 分组（参照 srw_alpha 用 SettingCardGroup 标题归组）：
        #   启动 / 界面设置 / MPV 插件 / 关于
        self.startup_group = self._create_group(
            "启动",
            [self.close_to_tray_card, self.autostart_card, self.auto_restore_card])
        self.ui_group = self._create_group(
            "界面设置", [self.theme_card, self.preview_text_card])
        self.mpv_group = self._create_group(
            "MPV 插件", [self.mpv_scripts_card, self.mpv_plugin_card])
        self.about_group = self._create_group(
            "关于", [self.about_card, self.update_card])

        sub_layout = QVBoxLayout()
        sub_layout.setContentsMargins(16, 16, 16, 16)
        sub_layout.addWidget(self.startup_group)
        sub_layout.addWidget(self.ui_group)
        sub_layout.addWidget(self.mpv_group)
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

    @staticmethod
    def _create_group(title: str, cards: list) -> SettingCardGroup:
        """创建带标题的设置卡片组（参照 srw_alpha 样式：标题 16pt、缩进 6、收紧标题间距）。"""
        group = SettingCardGroup(title)
        setFont(group.titleLabel, 16)
        group.titleLabel.setIndent(6)
        spacer = group.vBoxLayout.itemAt(1)
        if isinstance(spacer, QSpacerItem):
            spacer.changeSize(0, 5)
        for card in cards:
            group.addSettingCard(card)
        return group

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
