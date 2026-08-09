"""字体预览：注册字体文件并用其渲染样例文字。"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QFontDatabase, QTextOption
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import PlainTextEdit, SubtitleLabel, isDarkTheme, qconfig

from config import option
from core.models import FontEntry

_MAX_PREVIEW_LINES = 4  # 预览文本框最多显示的行数


class FontPreviewWidget(QWidget):
    """选中字体行的预览面板。TTC/OTC 按子字体序号取对应字面。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._family_cache: dict[str, str | None] = {}
        self._font_ids: dict[str, int] = {}  # 路径 → QFontDatabase 注册 ID，重命名前释放
        self._family: str | None = None
        self._italic = False
        self._weight = 400

        self.title = SubtitleLabel("—", self)
        # 防止标题在网格里被拉伸到整行高度（Preferred 垂直策略会被撑满）
        self.title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # 多行预览输入框：自动换行、最多显示 4 行；内容持久化到配置。
        # 不放入本面板布局——由编辑器页放到顶部控件区右侧、跨两行。
        self.sample_input = PlainTextEdit(self)
        self.sample_input.setPlainText(option.preview_sample.value)
        self.sample_input.setPlaceholderText("输入预览文字，支持多行换行…")
        self.sample_input.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.sample_input.setMaximumHeight(self._four_line_height())
        self.sample_input.setFixedWidth(600)

        # 预览渲染区：字体名 label 下方铺满
        self.preview_label = QLabel(self)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(48)
        self._apply_theme_color()

        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.preview_label, 1)
        self.setLayout(layout)

        # 内容变化：刷新预览 + 防抖写回配置（停止输入 600ms 后落盘）
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(600)
        self._save_timer.timeout.connect(self._persist_sample)
        self.sample_input.textChanged.connect(self._on_sample_changed)

    def _four_line_height(self) -> int:
        """按当前字体计算 4 行文本 + 输入框内边距的高度，超出后内部滚动。"""
        fm = self.sample_input.fontMetrics()
        return fm.lineSpacing() * _MAX_PREVIEW_LINES + 20

    def set_font(self, entry: FontEntry | None) -> None:
        """切换预览目标字体；None 表示清空。"""
        if entry is None:
            self._clear()
            return
        family = self._family_for(entry)
        self.title.setText(entry.display_name())
        self._family = family
        self._italic = entry.italic()
        self._weight = entry.us_weight_class
        self._render()

    def _clear(self) -> None:
        self.title.setText("—")
        self.preview_label.setText("（选择一行字体预览）")
        self._family = None
        self._italic = False
        self._weight = 400

    def _family_for(self, entry: FontEntry) -> str | None:
        path = entry.font_path
        if path in self._family_cache:
            return self._family_cache[path]
        family = None
        fam_id = QFontDatabase.addApplicationFont(path)
        if fam_id != -1:
            self._font_ids[path] = fam_id  # 记录注册 ID，供重命名前释放
            families = QFontDatabase.applicationFontFamilies(fam_id)
            if entry.is_collection and 0 <= entry.font_index < len(families):
                family = families[entry.font_index]
            else:
                preferred = entry.names["EN"][16] or entry.names["EN"][1] or ""
                family = next((f for f in families if f == preferred), None)
                if family is None and families:
                    family = families[0]
        self._family_cache[path] = family
        return family

    def release_font(self, path: str) -> None:
        """释放某字体的应用注册（重命名前调用），解除本进程对文件的占用锁。"""
        fam_id = self._font_ids.pop(path, None)
        if fam_id is not None:
            QFontDatabase.removeApplicationFont(fam_id)
        self._family_cache.pop(path, None)

    def refresh_theme(self) -> None:
        """主题切换后重绘预览：label 文字颜色按当前主题刷新。"""
        self._render()

    def _apply_theme_color(self) -> None:
        """按当前主题设置 label 文字颜色：深色白字、浅色黑字。

        qfw 切主题只刷样式表不更新全局 palette，普通 QLabel 不会自动变色，
        深色主题下黑字会看不见，这里显式覆盖。
        """
        color = "white" if isDarkTheme() else "black"
        self.preview_label.setStyleSheet(f"color: {color};")

    def _render(self) -> None:
        self._apply_theme_color()
        text = self.sample_input.toPlainText() or " "
        if self._family is None:
            self.preview_label.setFont(QFont("Microsoft YaHei UI", 24))
            self.preview_label.setText("（该字体无法预览）" if text != " " else "")
            return
        font = QFont(self._family, 24)
        font.setWeight(QFont.Weight(self._weight))  # usWeightClass(100-900) ≈ QFont.Weight
        font.setItalic(self._italic)
        self.preview_label.setFont(font)
        self.preview_label.setText(text)

    def _on_sample_changed(self) -> None:
        self._render()
        self._save_timer.start()  # 防抖：输入停顿后再写配置

    def _persist_sample(self) -> None:
        qconfig.set(option.preview_sample, self.sample_input.toPlainText())
