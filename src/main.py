"""拾字 GUI 入口。运行：python -B src/main.py"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from qfluentwidgets import setTheme, setThemeColor

from config import option
from core import qfw_compat
from core.single_instance import SingleInstance
from ui.main_window import MainWindow

import res  # 注册 qrc 编译的资源（:/icon.png、:/splash.png、:/html/help.html）


def _on_wake_request(window, single) -> None:
    """次实例请求唤醒：把主窗口带到前台（托盘态也会被唤出）。

    次实例连接成功即代表唤醒请求（写入的数据可忽略，客户端连上即发）。
    """
    server = single.server
    if server is None:
        return
    while server.hasPendingConnections():
        conn = server.nextPendingConnection()
        conn.disconnectFromServer()
    if not window.isVisible():
        window.show()
    window.raise_()
    window.activateWindow()


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    qfw_compat.apply()  # 注册修复后的 InfoBar 管理器，须先于任何 InfoBar 出现
    app = QApplication(sys.argv)
    setTheme(option.themeMode.value)
    setThemeColor(option.themeColor.value)

    single = SingleInstance()
    if not single.acquire():
        # 已有实例在运行：请它把窗口带到前台后退出，避免双开
        single.request_activate()
        return 0

    window = MainWindow()  # MainWindow 内部创建 SplashScreen 并在构建页面期间常驻
    window.show()
    if single.server is not None:
        single.server.newConnection.connect(lambda: _on_wake_request(window, single))

    code = app.exec()
    single.release()
    sys.exit(code)


if __name__ == "__main__":
    main()
