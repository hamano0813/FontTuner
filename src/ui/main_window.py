from PySide6.QtGui import QCloseEvent
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import MSFluentWindow, MessageBox, NavigationItemPosition

from ui.editor.frame import EditorFrame
from ui.settings.frame import SettingsFrame
from ui.signals import app_signals
from ui.templates.frame import TemplateFrame


class MainWindow(MSFluentWindow):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle("FontTuner")
        self.resize(1280, 800)
        self.setMinimumSize(960, 600)

        self.editor_frame = EditorFrame(self)
        self.template_frame = TemplateFrame(self)
        self.settings_frame = SettingsFrame(self)

        self.addSubInterface(self.editor_frame, FIF.EDIT, "字体编辑")
        self.addSubInterface(self.template_frame, FIF.BRUSH, "厂商模板")
        self.addSubInterface(self.settings_frame, FIF.SETTING, "设置",
                             position=NavigationItemPosition.BOTTOM)

        self._dirty = False
        app_signals.project_edited.connect(self._mark_dirty)
        app_signals.project_saved.connect(self._clear_dirty)

    def _mark_dirty(self):
        self._dirty = True

    def _clear_dirty(self):
        self._dirty = False

    def closeEvent(self, e: QCloseEvent):
        if self._dirty:
            box = MessageBox("未保存的修改", "有修改尚未保存，确定退出吗？", self)
            box.yesButton.setText("退出")
            box.cancelButton.setText("取消")
            if not box.exec():
                e.ignore()
                return
        super().closeEvent(e)
