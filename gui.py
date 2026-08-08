"""FontTuner GUI 入口（项目根目录）。"""

import os
import sys

# 把 src 加入模块搜索路径，使 core / ui / metadata 等可直接导入
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme

from ui.main_window import MainWindow


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    setTheme(Theme.AUTO)

    window = MainWindow()
    window.show()

    # 可选：拖拽/命令行传入的字体或文件夹，窗口就绪后预导入（不传也能正常启动）
    font_args = sys.argv[1:]
    if font_args:
        QTimer.singleShot(0, lambda: window.editor_frame.import_paths(font_args))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
