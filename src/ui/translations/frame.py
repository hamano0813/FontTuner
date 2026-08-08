"""字重/字宽翻译页：按语言分 Tab 编辑各语言标签，保存后对已加载字体立即生效。"""

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SegmentedWidget,
    SubtitleLabel,
)

from core import translations
from core.models import LANG_LABELS

_TAB_LANGS = ("SC", "TC", "JA", "EN")


class _LangTab(ScrollArea):
    """单个语言的字重/字宽标签编辑页：左列字重，右列字宽，顶部对齐。"""

    def __init__(self, lang: str, parent=None):
        super().__init__(parent)
        self.setObjectName(f"TransTab{lang}")
        self._lang = lang
        self.edits: dict[tuple, LineEdit] = {}

        content = QWidget(self)
        outer = QHBoxLayout(content)
        outer.setSpacing(40)

        # ---- 左列：字重 ----
        weight_widget = QWidget(content)
        weight_grid = QGridLayout(weight_widget)
        weight_grid.setSpacing(10)
        weight_grid.setColumnStretch(1, 1)

        weight_grid.addWidget(BodyLabel("字重", weight_widget), 0, 0, 1, 2)
        row = 1
        for value in sorted(translations.weight_labels("EN")):
            weight_grid.addWidget(
                CaptionLabel(f"{value} · {translations.weight_label(value, 'EN')}", weight_widget), row, 0)
            edit = LineEdit(weight_widget)
            edit.setText(translations.weight_label(value, lang))
            self.edits[("weight", value)] = edit
            weight_grid.addWidget(edit, row, 1)
            row += 1
        weight_grid.setRowStretch(row, 1)  # 行少时整体顶部对齐

        # ---- 右列：字宽 ----
        width_widget = QWidget(content)
        width_grid = QGridLayout(width_widget)
        width_grid.setSpacing(10)
        width_grid.setColumnStretch(1, 1)

        width_grid.addWidget(BodyLabel("字宽", width_widget), 0, 0, 1, 2)
        row = 1
        for value in sorted(translations.width_labels("EN")):
            width_grid.addWidget(
                CaptionLabel(f"{value} · {translations.width_label(value, 'EN')}", width_widget), row, 0)
            edit = LineEdit(width_widget)
            edit.setText(translations.width_label(value, lang))
            self.edits[("width", value)] = edit
            width_grid.addWidget(edit, row, 1)
            row += 1
        width_grid.setRowStretch(row, 1)  # 行少时整体顶部对齐

        outer.addWidget(weight_widget, 1)
        outer.addWidget(width_widget, 1)
        outer.addStretch(0)

        self.setWidget(content)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()

    def refresh(self) -> None:
        """从 translations 重新载入标签到输入框。"""
        for (kind, value), edit in self.edits.items():
            if kind == "weight":
                edit.setText(translations.weight_label(value, self._lang))
            else:
                edit.setText(translations.width_label(value, self._lang))


class TranslationFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("TranslationFrame")

        self.title = SubtitleLabel("字重/字宽翻译", self)
        self.hint = CaptionLabel(
            "标签用于子家族名自动生成与模板 {weight}/{width} 占位符；保存后对已加载字体立即生效。", self)

        self.segmented = SegmentedWidget(self)
        self.stack = QStackedWidget(self)
        self.tabs: dict[str, _LangTab] = {}
        for lang in _TAB_LANGS:
            tab = _LangTab(lang, self)
            self.tabs[lang] = tab
            self.stack.addWidget(tab)
            self.segmented.addItem(
                tab.objectName(), LANG_LABELS[lang],
                onClick=lambda checked=False, w=tab: self.stack.setCurrentWidget(w),
            )

        self.btn_reset = PushButton(FIF.SYNC, "恢复默认", self)
        self.btn_save = PrimaryPushButton(FIF.SAVE, "保存", self)
        self.btn_reset.clicked.connect(self._on_reset)
        self.btn_save.clicked.connect(self._on_save)

        btn_bar = QHBoxLayout()
        btn_bar.addStretch(1)
        btn_bar.addWidget(self.btn_reset)
        btn_bar.addWidget(self.btn_save)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.hint)
        layout.addSpacing(8)
        layout.addWidget(self.segmented)
        layout.addWidget(self.stack, 1)
        layout.addLayout(btn_bar)
        self.setLayout(layout)

    def _on_save(self) -> None:
        for lang, tab in self.tabs.items():
            for (kind, value), edit in tab.edits.items():
                label = edit.text().strip()
                if kind == "weight":
                    translations.set_weight_label(value, lang, label)
                else:
                    translations.set_width_label(value, lang, label)
        translations.save()
        self.window().editor_frame.refresh_after_translations()

    def _on_reset(self) -> None:
        translations.reset()
        for tab in self.tabs.values():
            tab.refresh()
        self.window().editor_frame.refresh_after_translations()
