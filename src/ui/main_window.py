from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QIcon, QPixmap
from PySide6.QtWidgets import QApplication
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import MSFluentWindow, MessageBox, NavigationItemPosition, SplashScreen

from config import option
from core.updater import read_version
from ui.editor.frame import EditorFrame
from ui.fontmgr.frame import FontManagerFrame
from ui.help.frame import HelpFrame
from ui.package.frame import PackageFrame
from ui.settings.frame import SettingsFrame
from ui.signals import app_signals
from ui.templates.frame import TemplateFrame
from ui.tray import TrayIcon


class MainWindow(MSFluentWindow):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        ver = read_version()
        self.setWindowTitle("拾字 FontTuner" if not ver else f"拾字 FontTuner v{ver}")
        self.setWindowIcon(QIcon(":/icon.png"))
        self.resize(1440, 720)
        self.setMinimumSize(960, 600)

        # 启动画面：qfw SplashScreen 铺满窗口，构建各页面期间常驻
        size = QSize(self.width(), self.height())
        self.splash = SplashScreen(
            QIcon(QPixmap(":/splash.png").scaled(
                size, mode=Qt.TransformationMode.SmoothTransformation)),
            self,
        )
        self.splash.setIconSize(size)

        self._dirty = False
        self._quitting = False          # 托盘「退出」放行标志：True 时才允许真正关闭
        self._tray_notified = False     # 首次最小化到托盘的提示只弹一次
        self.tray: TrayIcon | None = None
        app_signals.project_edited.connect(self._mark_dirty)
        app_signals.project_saved.connect(self._clear_dirty)

        # 先显示主窗口与 splash，再逐个构建页面（构建期间 splash 覆盖全窗口）
        # 注意：居中须在 show() 之后，否则 MSFluentWindow 的 4px 边框尚未建立，
        # frameGeometry 与 geometry 相同，居中出现 2px 偏差（splash 已覆盖，调整不可见）
        self.show()
        QApplication.processEvents()
        self._center_on_screen()

        self.editor_frame = EditorFrame(self)
        self.package_frame = PackageFrame(self)
        self.fontmgr_frame = FontManagerFrame(self)
        self.template_frame = TemplateFrame(self)
        self.help_frame = HelpFrame(self)
        self.settings_frame = SettingsFrame(self)

        self.addSubInterface(self.fontmgr_frame, FIF.LIBRARY, "字体管理")
        self.addSubInterface(self.package_frame, FIF.ZIP_FOLDER, "解包打包")
        self.addSubInterface(self.editor_frame, FIF.EDIT, "字体编辑")
        self.addSubInterface(self.template_frame, FIF.BRUSH, "信息模板")
        self.addSubInterface(self.settings_frame, FIF.SETTING, "设置",
                             position=NavigationItemPosition.BOTTOM)
        self.addSubInterface(self.help_frame, FIF.HELP, "帮助",
                             position=NavigationItemPosition.BOTTOM)

        self.splash.finish()

        # 启动画面结束 → 扩展窗口高度至 960（像 SRW：splash 阶段 720 打底，结束后增高）。
        # 高度不低于屏幕可用高度（留 20px 余量），避免小屏窗口超出屏幕。
        height = 960
        screen = QApplication.primaryScreen()
        if screen is not None:
            height = min(height, screen.availableGeometry().height() - 20)
        self.resize(1440, height)
        self._center_on_screen()

        # 常驻托盘图标：关闭窗口只最小化到托盘，托盘菜单「退出」才真正退出
        self.tray = TrayIcon(self)

    def _mark_dirty(self):
        self._dirty = True

    def _clear_dirty(self):
        self._dirty = False

    def _center_on_screen(self) -> None:
        """初始化窗口位置为当前屏幕居中。

        用 frameGeometry 计算，避免 MSFluentWindow 的 4px 边框使窗口右缘偏出 2px。
        """
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        frame = self.frameGeometry()
        self.move(
            rect.x() + (rect.width() - frame.width()) // 2,
            rect.y() + (rect.height() - frame.height()) // 2,
        )

    def reset_style(self):
        """主题切换后刷新所有控件的自定义样式。"""
        self.editor_frame.reset_style()
        self.help_frame.reset_style()

    def _request_quit(self):
        """托盘菜单「退出」：置放行标志后 close()，由 closeEvent 处理未保存再真正退出。

        用 singleShot(0) 延后到托盘菜单关闭之后再 close：若直接在托盘菜单动作里
        close，模态确认框会与正在关闭的托盘菜单竞争激活，导致确认框不出现、退出卡死。
        """
        self._quitting = True
        QTimer.singleShot(0, self.close)

    def closeEvent(self, e: QCloseEvent):
        # 托盘「退出」菜单，或关闭按钮在未开启「关闭到系统托盘」时 → 真正退出
        if self._quitting or not option.close_to_tray.value:
            self._quit(e)
            return

        # 点关闭按钮（开启「关闭到系统托盘」）→ 最小化到托盘，程序仍在运行
        if self.tray is None:
            # 托盘尚未就绪（极端时序），保持直接关闭
            super().closeEvent(e)
            return
        e.ignore()
        self.hide()
        if not self._tray_notified:
            self._tray_notified = True
            self.tray.notify(
                "拾字 FontTuner",
                "程序仍在运行，点击托盘图标可重新打开，右键菜单可退出。",
            )

    def _quit(self, e: QCloseEvent) -> None:
        """真正退出：先处理未保存，确认后才放行并退出事件循环。

        取消时恢复 _quitting 标志（仅托盘「退出」路径会置真），并忽略关闭事件
        保持运行。
        """
        if self._dirty:
            # 托盘态窗口已隐藏：先显示窗口，确认框才有可见父窗口。
            # 否则模态框以隐藏窗口为 owner，Windows 不激活/显示它，box.exec()
            # 空转导致退出卡死。
            if not self.isVisible():
                self.show()
                self.raise_()
                self.activateWindow()
            box = MessageBox("未保存的修改", "有修改尚未保存，确定退出吗？", self)
            box.yesButton.setText("退出")
            box.cancelButton.setText("取消")
            if not box.exec():
                self._quitting = False
                e.ignore()
                return
        super().closeEvent(e)
        # 托盘态窗口已隐藏，Qt「最后可见窗口关闭才退出」不会触发，
        # 必须显式退出事件循环，否则程序仍驻留托盘
        QApplication.instance().quit()
