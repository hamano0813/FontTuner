"""字重/字宽/斜体标签的跨语言翻译：默认值 + 用户覆盖，持久化到 data/translations.json。

引擎生成子家族名、模板 {weight} 占位符、表格下拉/显示 都从这里读取生效标签。
"""

from __future__ import annotations

import json
import os

from core.constants import FONT_WEIGHT, FONT_WIDTH
from core.paths import TRANSLATIONS_PATH

LANGS = ("EN", "SC", "TC", "JA")
_LANG_INDEX = {"EN": 0, "SC": 1, "TC": 2, "JA": 3}

# 生效标签 {lang: {value: label}}
_weight: dict[str, dict[int, str]] = {}
_width: dict[str, dict[int, str]] = {}
_italic: dict[str, dict[bool, str]] = {}


def _default_weight() -> dict[str, dict[int, str]]:
    return {
        lang: {v: (t[_LANG_INDEX[lang]] or t[0] or str(v)) for v, t in FONT_WEIGHT.items()}
        for lang in LANGS
    }


def _default_width() -> dict[str, dict[int, str]]:
    width = {
        lang: {v: (t[_LANG_INDEX[lang]] or t[0] or str(v)) for v, t in FONT_WIDTH.items()}
        for lang in LANGS
    }
    # 宽度 5（正常）：不产生宽度词，四种语言默认均空字符
    for lang in LANGS:
        width[lang][5] = ""
    return width


def _default_italic() -> dict[str, dict[bool, str]]:
    # 非斜体（False）：不产生斜体词，四种语言默认均空字符
    return {
        "EN": {False: "", True: "Italic"},
        "SC": {False: "", True: "斜体"},
        "TC": {False: "", True: "斜體"},
        "JA": {False: "", True: "I"},
    }


def load() -> None:
    """载入默认值 + 用户覆盖。"""
    global _weight, _width, _italic
    _weight = _default_weight()
    _width = _default_width()
    _italic = _default_italic()
    if not os.path.exists(TRANSLATIONS_PATH):
        return
    try:
        with open(TRANSLATIONS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return
    for lang, overrides in data.get("weight", {}).items():
        if lang in _weight:
            _weight[lang].update({int(v): lbl for v, lbl in overrides.items()})
    for lang, overrides in data.get("width", {}).items():
        if lang in _width:
            _width[lang].update({int(v): lbl for v, lbl in overrides.items()})
    for lang, overrides in data.get("italic", {}).items():
        if lang in _italic:
            # 保存写入的是 str(True)/str(False)，字符串比较需忽略大小写，否则两个键都判为 False
            _italic[lang].update({k.lower() == "true": lbl for k, lbl in overrides.items()})


def save() -> None:
    """把生效标签写回 data/translations.json。"""
    os.makedirs(os.path.dirname(TRANSLATIONS_PATH), exist_ok=True)
    data = {
        "weight": {lang: {str(v): lbl for v, lbl in _weight[lang].items()} for lang in LANGS},
        "width": {lang: {str(v): lbl for v, lbl in _width[lang].items()} for lang in LANGS},
        "italic": {lang: {str(k): lbl for k, lbl in _italic[lang].items()} for lang in LANGS},
    }
    with open(TRANSLATIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def reset() -> None:
    """恢复为常量默认，并清除覆盖文件。"""
    global _weight, _width, _italic
    _weight = _default_weight()
    _width = _default_width()
    _italic = _default_italic()
    if os.path.exists(TRANSLATIONS_PATH):
        os.remove(TRANSLATIONS_PATH)


# ---------------------------------------------------------------- 查询

def weight_label(value: int, lang: str = "SC") -> str:
    return _weight.get(lang, _weight["SC"]).get(value, str(value))


def width_label(value: int, lang: str = "SC") -> str:
    return _width.get(lang, _width["SC"]).get(value, str(value))


def italic_label(flag: bool, lang: str = "SC") -> str:
    return _italic.get(lang, _italic["SC"]).get(bool(flag), "")


def weight_labels(lang: str) -> dict[int, str]:
    return dict(_weight.get(lang, {}))


def width_labels(lang: str) -> dict[int, str]:
    return dict(_width.get(lang, {}))


def lang_of(lang_id: int) -> str:
    """Windows 语言 ID → 逻辑语言（未识别回落英文）。"""
    if lang_id == 0x0804:
        return "SC"
    if lang_id == 0x0404:
        return "TC"
    if lang_id == 0x0411:
        return "JA"
    return "EN"


# ---------------------------------------------------------------- 编辑

def set_weight_label(value: int, lang: str, label: str) -> None:
    _weight[lang][value] = label


def set_width_label(value: int, lang: str, label: str) -> None:
    _width[lang][value] = label


def set_italic_label(flag: bool, lang: str, label: str) -> None:
    _italic[lang][bool(flag)] = label


load()  # 模块导入即载入生效标签
