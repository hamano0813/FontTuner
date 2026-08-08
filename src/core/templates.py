"""厂商模板：字段集 + JSON 持久化 + 一键应用。"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field

from core.models import CHARSET_TEMP_CODES, LANGS, NAME_TEMP_CODES, FontEntry
from core.paths import TEMPLATES_PATH

# 模板可设置的字段：版权/商标/厂商/设计者/描述/厂商网址/许可网址/许可
TEMPLATE_NAME_IDS = [0, 7, 8, 9, 10, 11, 12, 13]


@dataclass
class VendorTemplate:
    name: str
    field_values: dict[str, dict[int, str]] = field(default_factory=dict)
    # lang_key("ALL"/"SC"/"TC"/"JA"/"EN") -> {nameID: value}
    # 字重/字宽/斜体不属于模板，应用模板不操作这些


def load_templates(path: str | None = None) -> list[VendorTemplate]:
    path = path or TEMPLATES_PATH
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    return [VendorTemplate(**item) for item in data]


def save_templates(templates: list[VendorTemplate], path: str | None = None) -> None:
    path = path or TEMPLATES_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(t) for t in templates], f, ensure_ascii=False, indent=2)


def apply_template(entry: FontEntry, tmpl: VendorTemplate) -> None:
    """把模板字段应用到单个字体，并自动勾选受影响语言的保存开关。

    文本字段含 `{...}` 时按该字体的字重/字宽/斜体/临时名称/字符集动态格式化。
    """
    all_values = tmpl.field_values.get("ALL", {})
    for lang in LANGS:
        values = dict(all_values)
        values.update(tmpl.field_values.get(lang, {}))
        if not values:
            continue
        for name_id, text in values.items():
            if "{" in text:
                text = format_name(text, entry, lang)
            entry.names[lang][name_id] = text
        entry.save_langs[lang] = True  # 模板可新建该语言记录


# ---------------------------------------------------------------- 格式化

class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"  # 未识别的占位符原样保留


def format_name(text: str, entry: FontEntry, lang: str) -> str:
    """把含 {weight}/{width}/{italic} 等占位符的模板文本按字体动态生成。"""
    if "{" not in text:
        return text
    try:
        return text.format_map(_SafeDict(_format_vars(entry, lang)))
    except (KeyError, IndexError, ValueError):
        return text  # 格式不合法时原样保留


def _format_vars(entry: FontEntry, lang: str) -> dict[str, object]:
    from core.translations import italic_label, weight_label, width_label

    vars = {
        "weight": weight_label(entry.us_weight_class, lang),
        "width": width_label(entry.us_width_class, lang),
        "italic": italic_label(entry.italic(), lang),
        "weight_num": entry.us_weight_class,
        "width_num": entry.us_width_class,
    }
    # 表格头部 4 个临时名称：{name_sc}/{name_tc}/{name_jp}/{name_en}
    for lang, code in NAME_TEMP_CODES.items():
        vars[code] = entry.temp_names[lang]
    # 字符集 4 列：{charset_sc}/{charset_tc}/{charset_jp}/{charset_en}
    for lang, code in CHARSET_TEMP_CODES.items():
        vars[code] = entry.charsets[lang]
    return vars
