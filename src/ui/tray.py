"""系统托盘：常驻任务栏图标。

配合 MainWindow 的 closeEvent：点关闭按钮 → 最小化到托盘（程序仍运行），
托盘菜单「显示主界面」重新打开、「退出」才真正退出（经 closeEvent 处理未保存后放行）。
菜单与点击样式参照 qfw 的 SystemTrayMenu 写法。
"""

from __future__ import annotations

from PySide6.QtWidgets import QSystemTrayIcon
from qfluentwidgets import Action, SystemTrayMenu


class TrayIcon(QSystemTrayIcon):
    """常驻托盘图标：菜单含「显示主界面」「退出」，单击图标即重新打开主窗口。"""

    def __init__(self, window, parent=None):
        super().__init__(parent=parent)
        self.window = window
        self.setIcon(window.windowIcon())
        self.setToolTip(window.windowTitle())

        self.menu = SystemTrayMenu(parent=parent or window)
        self.menu.addActions([
            Action("显示主界面", triggered=self._show_window),
        ])
        self.menu.addSeparator()
        self.menu.addActions([
            Action("退出", triggered=self._quit_app),
        ])
        self.setContextMenu(self.menu)

        self.activated.connect(self._on_activated)
        self.show()

    # ---------- 动作 ----------

    def _show_window(self):
        win = self.window
        win.show()
        win.raise_()
        win.activateWindow()

    def _quit_app(self):
        self.window._request_quit()

    def _on_activated(self, reason):
        # 单击/双击托盘图标 → 重新打开主窗口
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._show_window()

    def notify(self, title: str, body: str, ms: int = 3000):
        self.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, ms)
