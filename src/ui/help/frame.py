"""帮助页面：把 README.md 编译的 HTML（打包进 qrc 资源）用 TextBrowser 渲染。

make_help.py（pandoc --embed-resources + 自定义模板）将 README.md 转为纯 HTML body
片段（res/html/help.html），经 res.qrc 编译进 src/res.py，运行期通过 `:/html/help.html`
读取，由 qfluentwidgets 的 TextBrowser 渲染。

页面样式不写在 HTML 里，而是运行期按当前明暗主题注入（QTextDocument 支持
setDefaultStyleSheet 的元素/类选择器）：明/暗两套 GitHub 风格配色，覆盖标题、链接、
引用块、行内 code、pre 代码块与表格边框表头，主题切换时自动重渲染。
"""

from PySide6.QtCore import QFile, QIODevice, Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout
from qfluentwidgets import TextBrowser, isDarkTheme, setCustomStyleSheet, setFont

# 控件背景：跟随 MSFluentWindow 页面底色
LIGHT_QSS = "#HELP, #HELP:hover, #HELP:focus { background-color: transparent; }"
DARK_QSS = "#HELP, #HELP:hover, #HELP:focus { background-color: rgba(32, 32, 32, 0.5); }"

# 文档样式（GitHub 风格明/暗配色）。QTextDocument 支持元素/类/后代选择器，
# 但仅支持有限的 CSS 子集（不支持 line-height、margin 百分比等）。
LIGHT_CSS = """
body { color: #1f2328; }
h1 { color: #1f2328; font-size: 28px; margin-top: 8px; }
h2 { color: #1f2328; font-size: 22px; margin-top: 30px; }
h3 { color: #1f2328; font-size: 18px; margin-top: 24px; }
h1, h2, h3 { font-weight: 600; }
a { color: #0969da; }
blockquote { color: #57606a; border-left: 4px solid #d0d7de; padding-left: 12px; }
code { color: #cf222e; background-color: #f6f8fa; padding: 2px 4px; }
pre { background-color: #f6f8fa; border: 1px solid #d0d7de; padding: 10px; }
pre code { color: #1f2328; background-color: transparent; padding: 0; }
table { border-collapse: collapse; }
th { background-color: #f6f8fa; border: 1px solid #d0d7de; padding: 6px 10px; font-weight: 600; }
td { border: 1px solid #d0d7de; padding: 6px 10px; }
"""

DARK_CSS = """
body { color: #c9d1d9; }
h1 { color: #e6edf3; font-size: 28px; margin-top: 8px; }
h2 { color: #e6edf3; font-size: 22px; margin-top: 30px; }
h3 { color: #e6edf3; font-size: 18px; margin-top: 24px; }
h1, h2, h3 { font-weight: 600; }
a { color: #58a6ff; }
blockquote { color: #8b949e; border-left: 4px solid #30363d; padding-left: 12px; }
code { color: #ff7b72; background-color: #21262d; padding: 2px 4px; }
pre { background-color: #161b22; border: 1px solid #30363d; padding: 10px; }
pre code { color: #c9d1d9; background-color: transparent; padding: 0; }
table { border-collapse: collapse; }
th { background-color: #21262d; border: 1px solid #30363d; padding: 6px 10px; font-weight: 600; }
td { border: 1px solid #30363d; padding: 6px 10px; }
"""


class HelpFrame(QFrame):
    """帮助页面：显示 README 编译的 HTML 说明。"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("HelpFrame")

        self._html = None  # 缓存帮助 HTML，主题切换后重渲染

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
            self._html = qfile.readAll().data().decode("utf-8")
            qfile.close()
        self._render()

    def _render(self) -> None:
        """按当前明暗主题注入文档样式后渲染。

        setDefaultStyleSheet 须在 setHtml 之前调用，故主题切换（reset_style）
        时需重设样式表并重新 setHtml。
        """
        if self._html is None:
            self._browser.setPlainText("帮助文件未找到，请重新安装程序。")
            return
        self._browser.document().setDefaultStyleSheet(
            DARK_CSS if isDarkTheme() else LIGHT_CSS
        )
        self._browser.setHtml(self._html)

    # ---------------------------------------------------------------- 主题

    def reset_style(self) -> None:
        """刷新字体与配色，主题切换后由 MainWindow.reset_style 调用。"""
        setFont(self._browser)
        setCustomStyleSheet(
            self._browser,
            LIGHT_QSS,
            DARK_QSS,
        )
        self._browser.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        if self._html is not None:
            self._render()
