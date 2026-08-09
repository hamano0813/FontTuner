"""帮助页面：把 README.md 编译的 HTML（打包进 qrc 资源）用 TextBrowser 渲染。

pandoc 将 README.md 转为纯 HTML body 片段（res/html/help.html），经 res.qrc 编译进
src/res.py，运行期通过 `:/html/help.html` 读取，由 qfluentwidgets 的 TextBrowser 渲染，
自动跟随应用明暗主题。
"""

from PySide6.QtCore import QFile, QIODevice, Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout
from qfluentwidgets import TextBrowser, setCustomStyleSheet, setFont


class HelpFrame(QFrame):
    """帮助页面：显示 README 编译的 HTML 说明。"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("HelpFrame")

        self._browser = TextBrowser(self)
        self._browser.setObjectName("HELP")
        self._browser.setOpenExternalLinks(True)
        self._browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._browser.setViewportMargins(60, 30, 60, 30)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._browser)

        self.reset_style()
        self._load_help()

    # ---------------------------------------------------------------- 加载

    def _load_help(self) -> None:
        """从 qrc 资源读取 README 编译的 HTML。"""
        qfile = QFile(":/html/help.html")
        if qfile.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
            html = qfile.readAll().data().decode("utf-8")
            qfile.close()
            self._browser.setHtml(html)
        else:
            self._browser.setPlainText("帮助文件未找到，请重新安装程序。")

    # ---------------------------------------------------------------- 主题

    def reset_style(self) -> None:
        """刷新字体与背景配色，主题切换后由 MainWindow.reset_style 调用。"""
        setFont(self._browser)
        setCustomStyleSheet(
            self._browser,
            "#HELP, #HELP:hover, #HELP:focus { background-color: transparent; }",
            "#HELP, #HELP:hover, #HELP:focus { background-color: rgba(32, 32, 32, 0.5); }",
        )
        self._browser.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
