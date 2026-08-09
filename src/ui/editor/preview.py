"""字体预览：注册字体文件并用其渲染样例文字。"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import SpinBox, SubtitleLabel, isDarkTheme, qconfig

from config import option
from core.models import FontEntry


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

        # 预览字号 spinbox：标题右侧右对齐，改字号即时重绘并持久化
        self._preview_size = option.preview_font_size.value
        self.size_spin = SpinBox(self)
        self.size_spin.setRange(8, 72)
        self.size_spin.setValue(self._preview_size)
        self.size_spin.setToolTip("预览字号（点）")
        self.size_spin.valueChanged.connect(self._on_size_changed)

        # 预览渲染区：字体名 label 下方铺满
        self.preview_label = QLabel(self)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(48)
        self._apply_theme_color()

        layout = QVBoxLayout(self)
        size_row = QHBoxLayout()
        size_row.addWidget(self.title)
        size_row.addStretch(1)
        size_row.addWidget(self.size_spin)
        layout.addLayout(size_row)
        layout.addWidget(self.preview_label, 1)
        self.setLayout(layout)

        # 预览文字来自设置页的 option.preview_sample，改动时即时重绘
        option.preview_sample.valueChanged.connect(self._render)

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
        text = option.preview_sample.value or " "
        if self._family is None:
            self.preview_label.setFont(QFont("Microsoft YaHei UI", self._preview_size))
            self.preview_label.setText("（该字体无法预览）" if text != " " else "")
            return
        font = QFont(self._family, self._preview_size)
        font.setWeight(QFont.Weight(self._weight))  # usWeightClass(100-900) ≈ QFont.Weight
        font.setItalic(self._italic)
        self.preview_label.setFont(font)
        self.preview_label.setText(text)

    def _on_size_changed(self, value: int) -> None:
        """预览字号变更：重绘并立即写回配置。"""
        self._preview_size = value
        qconfig.set(option.preview_font_size, value)
        self._render()
