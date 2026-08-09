from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCloseEvent, QIcon, QPixmap
from PySide6.QtWidgets import QApplication
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import MSFluentWindow, MessageBox, NavigationItemPosition, SplashScreen

from ui.editor.frame import EditorFrame
from ui.fontmgr.frame import FontManagerFrame
from ui.help.frame import HelpFrame
from ui.package.frame import PackageFrame
from ui.settings.frame import SettingsFrame
from ui.signals import app_signals
from ui.templates.frame import TemplateFrame
from ui.translations.frame import TranslationFrame


class MainWindow(MSFluentWindow):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle("拾字 FontTuner")
        self.setWindowIcon(QIcon(":/icon.png"))
        self.resize(1440, 720)
        self.setMinimumSize(960, 600)

        # 启动画面（参考 srw_alpha）：qfw SplashScreen 铺满窗口，构建各页面期间常驻
        size = QSize(self.width(), self.height())
        self.splash = SplashScreen(
            QIcon(QPixmap(":/splash.png").scaled(
                size, mode=Qt.TransformationMode.SmoothTransformation)),
            self,
        )
        self.splash.setIconSize(size)

        self._dirty = False
        app_signals.project_edited.connect(self._mark_dirty)
        app_signals.project_saved.connect(self._clear_dirty)

        # 先显示主窗口与 splash，再逐个构建页面（构建期间 splash 覆盖全窗口）
        self.show()
        QApplication.processEvents()

        self.editor_frame = EditorFrame(self)
        self.package_frame = PackageFrame(self)
        self.fontmgr_frame = FontManagerFrame(self)
        self.template_frame = TemplateFrame(self)
        self.translation_frame = TranslationFrame(self)
        self.help_frame = HelpFrame(self)
        self.settings_frame = SettingsFrame(self)

        self.addSubInterface(self.fontmgr_frame, FIF.LIBRARY, "字体管理")
        self.addSubInterface(self.package_frame, FIF.ZIP_FOLDER, "解包打包")
        self.addSubInterface(self.editor_frame, FIF.EDIT, "字体编辑")
        self.addSubInterface(self.template_frame, FIF.BRUSH, "信息模板")
        self.addSubInterface(self.translation_frame, FIF.FONT, "翻译方案")
        self.addSubInterface(self.settings_frame, FIF.SETTING, "设置",
                             position=NavigationItemPosition.BOTTOM)
        self.addSubInterface(self.help_frame, FIF.HELP, "帮助",
                             position=NavigationItemPosition.BOTTOM)

        self.splash.finish()

    def _mark_dirty(self):
        self._dirty = True

    def _clear_dirty(self):
        self._dirty = False

    def reset_style(self):
        """主题切换后刷新所有控件的自定义样式。"""
        self.editor_frame.reset_style()
        self.help_frame.reset_style()

    def closeEvent(self, e: QCloseEvent):
        if self._dirty:
            box = MessageBox("未保存的修改", "有修改尚未保存，确定退出吗？", self)
            box.yesButton.setText("退出")
            box.cancelButton.setText("取消")
            if not box.exec():
                e.ignore()
                return
        super().closeEvent(e)
