"""字体预览：注册字体文件并用其渲染样例文字。"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, SubtitleLabel

from core.models import FontEntry

DEFAULT_SAMPLE = "中文字体 简体 繁體 日本語 ABC abc 0123"


class FontPreviewWidget(QWidget):
    """选中字体行的预览面板。TTC/OTC 按子字体序号取对应字面。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._family_cache: dict[str, str | None] = {}

        self.title = SubtitleLabel("—", self)
        self.sample_input = QLineEdit(DEFAULT_SAMPLE, self)
        self.sample_input.setClearButtonEnabled(True)
        self.preview_label = QLabel(self)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(48)

        top = QHBoxLayout()
        top.addWidget(self.title)
        top.addStretch(1)
        top.addWidget(self.sample_input, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.preview_label, 1)
        self.setLayout(layout)

        self.sample_input.textChanged.connect(self._render)

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

    def _render(self) -> None:
        text = self.sample_input.text() or " "
        if self._family is None:
            self.preview_label.setFont(QFont("Microsoft YaHei UI", 24))
            self.preview_label.setText("（该字体无法预览）" if text != " " else "")
            return
        font = QFont(self._family, 24)
        font.setWeight(QFont.Weight(self._weight))  # usWeightClass(100-900) ≈ QFont.Weight
        font.setItalic(self._italic)
        self.preview_label.setFont(font)
        self.preview_label.setText(text)
