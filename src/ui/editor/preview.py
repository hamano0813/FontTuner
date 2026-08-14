"""字体预览：注册字体文件并用其渲染样例文字。"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from qfluentwidgets import isDarkTheme, qconfig

from config import option
from core.models import FontEntry


class FontPreviewWidget(QWidget):
    """选中字体行的预览面板：只渲染预览文字（设置页配置），无标题/无字号控件。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._family_cache: dict[tuple, str | None] = {}  # (path, font_index) → 家族名
        self._font_ids: dict[str, int] = {}  # 路径 → QFontDatabase 注册 ID，重命名前释放
        self._family: str | None = None
        self._italic = False
        self._weight = 400

        # 预览渲染区：铺满
        self.preview_label = QLabel(self)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(48)
        self._apply_theme_color()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.preview_label, 1)
        self.setLayout(layout)

        # 预览文字/字号由设置页的 option 配置，改动时即时重绘
        option.preview_sample.valueChanged.connect(self._render)
        option.preview_font_size.valueChanged.connect(self._render)

    def set_font(self, entry: FontEntry | None) -> None:
        """切换预览目标字体；None 表示清空。"""
        if entry is None:
            self._clear()
            return
        family = self._family_for(entry)
        self._family = family
        self._italic = entry.italic()
        self._weight = entry.us_weight_class
        self._render()

    def _clear(self) -> None:
        self.preview_label.setText("（选择一行字体预览）")
        self._family = None
        self._italic = False
        self._weight = 400

    def _family_for(self, entry: FontEntry) -> str | None:
        # 缓存 key 必须含 face 序号：同一 TTC/OTC 的各 face 行路径相同，
        # 若只按 path 缓存会全部命中第一个 face，预览看不出区别
        key = (entry.font_path, entry.font_index)
        if key in self._family_cache:
            return self._family_cache[key]
        path = entry.font_path
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
        self._family_cache[key] = family
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
        text = option.preview_sample.value or " "
        size = option.preview_font_size.value
        if self._family is None:
            self.preview_label.setFont(QFont("Microsoft YaHei UI", size))
            self.preview_label.setText("（该字体无法预览）" if text != " " else "")
            return
        font = QFont(self._family, size)
        font.setWeight(QFont.Weight(self._weight))  # usWeightClass(100-900) ≈ QFont.Weight
        font.setItalic(self._italic)
        self.preview_label.setFont(font)
        self.preview_label.setText(text)
