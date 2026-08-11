"""字重/字宽/斜体翻译页：按语言分 Tab 编辑各语言标签，保存后对已加载字体立即生效。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CaptionLabel,
    FluentIcon as FIF,
    HeaderCardWidget,
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
    """单个语言的字重/字宽/斜体翻译页：左字重卡，右字宽卡+斜体卡（纵向叠放）。
    卡体行布局与原来一致：单列 值·EN标签 | 输入框。"""

    def __init__(self, lang: str, parent=None):
        super().__init__(parent)
        self.setObjectName(f"TransTab{lang}")
        self._lang = lang
        self.edits: dict[tuple, LineEdit] = {}

        content = QWidget(self)
        outer = QHBoxLayout(content)
        outer.setSpacing(12)

        # ---- 左：字重卡 ----
        weight_card = HeaderCardWidget("字重", content)
        self._fill_rows(
            weight_card,
            sorted(translations.weight_labels("EN")),
            label_fn=lambda v: f"{v} · {translations.weight_label(v, 'EN')}",
            getter_fn=lambda v: translations.weight_label(v, lang),
            key_fn=lambda v: ("weight", v),
        )
        outer.addWidget(weight_card, 1)

        # ---- 右：字宽卡 + 斜体卡（纵向叠放）----
        right = QWidget(content)
        right_box = QVBoxLayout(right)
        right_box.setSpacing(12)

        width_card = HeaderCardWidget("字宽", content)
        self._fill_rows(
            width_card,
            sorted(translations.width_labels("EN")),
            label_fn=lambda v: f"{v} · {translations.width_label(v, 'EN')}",
            getter_fn=lambda v: translations.width_label(v, lang),
            key_fn=lambda v: ("width", v),
        )
        right_box.addWidget(width_card)

        italic_card = HeaderCardWidget("斜体", content)
        self._fill_rows(
            italic_card,
            [False, True],
            label_fn=lambda f: f"{'正常' if not f else '斜体'} · {translations.italic_label(f, 'EN')}",
            getter_fn=lambda f: translations.italic_label(f, lang),
            key_fn=lambda f: ("italic", f),
        )
        right_box.addWidget(italic_card)
        right_box.addStretch(1)

        outer.addWidget(right, 1)

        self.setWidget(content)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()

    def _fill_rows(self, card, values, label_fn, getter_fn, key_fn) -> None:
        """卡体行布局：单列 (值·EN标签 | 输入框)，与原来保持一致。"""
        body = QWidget(card)
        grid = QGridLayout(body)
        grid.setSpacing(10)
        grid.setColumnStretch(1, 1)
        for row, value in enumerate(values):
            grid.addWidget(CaptionLabel(label_fn(value), body), row, 0)
            edit = LineEdit(body)
            edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)  # 输入框禁用右键菜单
            edit.setText(getter_fn(value))
            self.edits[key_fn(value)] = edit
            grid.addWidget(edit, row, 1)
        grid.setRowStretch(len(values), 1)  # 行少时卡体内整体顶部对齐
        card.viewLayout.addWidget(body)

    def refresh(self) -> None:
        """从 translations 重新载入标签到输入框。"""
        for (kind, value), edit in self.edits.items():
            if kind == "weight":
                edit.setText(translations.weight_label(value, self._lang))
            elif kind == "width":
                edit.setText(translations.width_label(value, self._lang))
            else:  # italic
                edit.setText(translations.italic_label(value, self._lang))


class TranslationFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("TranslationFrame")

        self.title = SubtitleLabel("字重/字宽/斜体翻译", self)
        self.hint = CaptionLabel(
            "标签用于子家族名自动生成及模板占位符 {weight}/{width}/{italic}；保存后对已加载字体立即生效。", self)

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
                elif kind == "width":
                    translations.set_width_label(value, lang, label)
                else:  # italic
                    translations.set_italic_label(value, lang, label)
        translations.save()
        self.window().editor_frame.refresh_after_translations()

    def _on_reset(self) -> None:
        translations.reset()
        for tab in self.tabs.values():
            tab.refresh()
        self.window().editor_frame.refresh_after_translations()
