"""拾字 GUI 入口。运行：python -B src/main.py"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from qfluentwidgets import setTheme, setThemeColor

from config import option
from core import qfw_compat
from ui.main_window import MainWindow

import res  # 注册 qrc 编译的资源（:/icon.png、:/splash.png、:/html/help.html）


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    qfw_compat.apply()  # 注册修复后的 InfoBar 管理器，须先于任何 InfoBar 出现
    app = QApplication(sys.argv)
    setTheme(option.themeMode.value)
    setThemeColor(option.themeColor.value)

    window = MainWindow()  # MainWindow 内部创建 SplashScreen 并在构建页面期间常驻
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
