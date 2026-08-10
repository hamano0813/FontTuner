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


def _set_windows_app_id() -> None:
    """给托盘通知一个稳定的应用身份（Windows）。

    通知中心顶部显示的应用名取自进程身份：进程不设 AppUserModelID 时，系统
    为它的托盘通知生成随机 AUMID（NotifyIconGeneratedAumid_*）并回退显示进程
    名——开发态/打包态都是 python/pythonw，通知标题就成了「python」。显式
    SetCurrentProcessExplicitAppUserModelID 后归属变为「FontTuner」。须先于
    QApplication 创建、任何托盘通知之前调用。
    """
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FontTuner")


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
    _set_windows_app_id()  # 通知中心归属「FontTuner」，须先于 QApplication/托盘通知
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    qfw_compat.apply()  # 注册修复后的 InfoBar 管理器，须先于任何 InfoBar 出现
    app = QApplication(sys.argv)
    app.setApplicationName("FontTuner")
    app.setApplicationDisplayName("拾字 FontTuner")
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
