"""FontTuner GUI 入口。运行：python -B src/main.py"""

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication
from qfluentwidgets import setTheme, setThemeColor

from config import option
from ui.main_window import MainWindow


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    setTheme(option.themeMode.value)
    setThemeColor(option.themeColor.value)

    window = MainWindow()
    window.show()

    # 可选：拖拽/命令行传入的字体或文件夹，窗口就绪后预导入（不传也能正常启动）
    font_args = sys.argv[1:]
    if font_args:
        QTimer.singleShot(0, lambda: window.editor_frame.import_paths(font_args))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
