"""拾字 GUI 入口。运行：python -B src/main.py"""

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication
from qfluentwidgets import setTheme, setThemeColor

from config import option
from ui.main_window import MainWindow


def _patch_qfw_info_bar() -> None:
    """消除 qfw InfoBar 的装饰性告警。

    InfoBarManager.add 里创建的 dropAni 只设时长、未设端值，真实窗口时序下
    动画被 start 时 Qt 报 `QPropertyAnimation::updateState (pos, InfoBar): starting
    an animation without end value`。补丁在 add() 后立即补上 start/end，告警消失。
    """
    from qfluentwidgets.components.widgets.info_bar import InfoBarManager
    if getattr(InfoBarManager, "_patched", False):
        return
    _orig_add = InfoBarManager.add

    def _add(self, infoBar):
        _orig_add(self, infoBar)
        drop = infoBar.property("dropAni")
        if drop is not None and drop.endValue() is None:
            drop.setStartValue(infoBar.pos())
            drop.setEndValue(self._pos(infoBar))

    InfoBarManager.add = _add
    InfoBarManager._patched = True


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    _patch_qfw_info_bar()  # 先于任何 InfoBar 出现前生效
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
