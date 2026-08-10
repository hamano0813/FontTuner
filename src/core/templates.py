"""信息模板：字段集 + JSON 持久化 + 一键应用。"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field

from core import translations
from core.models import CHARSET_TEMP_CODES, LANGS, NAME_TEMP_CODES, FontEntry
from core.paths import TEMPLATES_PATH

# 模板可设置的字段：全部 name 字段，排除子家族名(2)。
# 子家族名在应用模板时按字重隐式写 Bold/Regular，不靠模板编辑。
TEMPLATE_NAME_IDS = [0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 256, 257, 258]
# 应用模板时不从模板读取的字段（兼容旧模板 JSON 里的残留值）
_TEMPLATE_SKIP_IDS = (2,)


@dataclass
class VendorTemplate:
    name: str
    field_values: dict[str, dict[int, str]] = field(default_factory=dict)
    # lang_key("ALL"/"SC"/"TC"/"JA"/"EN") -> {nameID: value}
    translations: dict[str, dict[str, dict]] = field(default_factory=dict)
    # lang_key("SC"/"TC"/"JA"/"EN") -> {"weight": {value: label}, "width": {...}, "italic": {bool: label}}
    # 捆绑该厂商的字重/字宽/斜体标签；应用模板时写入全局翻译字典并持久化


def load_templates(path: str | None = None) -> list[VendorTemplate]:
    path = path or TEMPLATES_PATH
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    templates = []
    for item in data:
        # JSON 对象键恒为字符串，nameID 键需还原为 int，否则编辑回填/应用写入都查不到
        field_values = {
            lang: {int(nid): text for nid, text in values.items()}
            for lang, values in item.get("field_values", {}).items()
        }
        # 翻译键同样还原：weight/width 键回 int，italic 键回 bool
        translations_data: dict[str, dict] = {}
        for lang, kinds in item.get("translations", {}).items():
            parsed: dict[str, dict] = {}
            for kind, values in kinds.items():
                if kind == "italic":
                    parsed[kind] = {k.lower() == "true": lbl for k, lbl in values.items()}
                else:
                    parsed[kind] = {int(v): lbl for v, lbl in values.items()}
            translations_data[lang] = parsed
        item = dict(item)
        item["field_values"] = field_values
        item["translations"] = translations_data
        templates.append(VendorTemplate(**item))
    return templates


def save_templates(templates: list[VendorTemplate], path: str | None = None) -> None:
    path = path or TEMPLATES_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(t) for t in templates], f, ensure_ascii=False, indent=2)


def apply_template(entry: FontEntry, tmpl: VendorTemplate) -> None:
    """把模板字段应用到单个字体，并自动勾选受影响语言的保存开关。

    模板中为空的字段不覆盖，保留字体原有值；模板文本原样写入，
    含 `{...}` 占位符的字段不做展开，留给「解析」按钮/保存时解析。
    子家族名(2) 不从模板读取；对勾选保存的语言隐式写固定文本：
    字重 700 → Bold，其余 → Regular（不分语言）。
    """
    all_values = tmpl.field_values.get("ALL", {})
    for lang in LANGS:
        values = dict(all_values)
        values.update(tmpl.field_values.get(lang, {}))
        if not values:
            continue
        for name_id, text in values.items():
            if name_id in _TEMPLATE_SKIP_IDS:
                continue  # 版权/子家族名不靠模板编辑
            if not text or not text.strip():
                continue  # 模板字段为空 → 跳过，保留字体原有值
            entry.names[lang][name_id] = text
            entry.save_langs[lang] = True  # 模板可新建该语言记录
    # 子家族名隐式设置：勾选保存的语言统一写固定文本（不分语言）
    subfamily = "Bold" if entry.us_weight_class == 700 else "Regular"
    for lang in LANGS:
        if entry.save_langs[lang]:
            entry.names[lang][2] = subfamily


def apply_translations(tmpl: VendorTemplate) -> int:
    """把模板捆绑的字重/字宽/斜体标签写入全局翻译字典并持久化。

    模板中为空的标签跳过，保留全局当前值；非空标签覆盖对应 (值, 语言)。
    返回实际写入的标签数。translations.save() 把生效标签落盘，重启后
    仍保持该厂商术语。
    """
    count = 0
    for lang, kinds in tmpl.translations.items():
        for kind, values in kinds.items():
            for value, label in values.items():
                if not label or not label.strip():
                    continue
                if kind == "weight":
                    translations.set_weight_label(int(value), lang, label)
                elif kind == "width":
                    translations.set_width_label(int(value), lang, label)
                elif kind == "italic":
                    translations.set_italic_label(bool(value), lang, label)
                else:
                    continue
                count += 1
    translations.save()
    return count


def resolve_entry_placeholders(entry: FontEntry, langs: tuple = LANGS) -> int:
    """把 entry 各语言 name 字段中的 `{占位符}` 就地解析为正常文本。

    等价于保存时 build_font_setting 里的隐式解析，这里提前落进表格，
    让用户直接看到最终文本。无占位符的字段跳过。返回解析的字段数。
    """
    count = 0
    for lang in langs:
        names = entry.names[lang]
        for name_id, value in list(names.items()):
            if "{" in value:
                names[name_id] = format_name(value, entry, lang)
                count += 1
    return count


# ---------------------------------------------------------------- 格式化

_EMPTY_SENTINEL = "\x00"  # 解析为空文本的占位符哨兵，连同前导空白一并删除


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"  # 未识别的占位符原样保留


def format_name(text: str, entry: FontEntry, lang: str) -> str:
    """把含 {weight}/{width}/{italic} 等占位符的模板文本按字体动态生成。

    占位符解析为空文本时，连同其前导空白一并删除
    （如 "A {width}" → "A"，"A {width} B" → "A B"）。
    """
    if "{" not in text:
        return text
    vars = {
        # 仅空字符串视为空（weight_num/width_num 等数值 0 不误判）
        k: (_EMPTY_SENTINEL if isinstance(v, str) and not v else v)
        for k, v in _format_vars(entry, lang).items()
    }
    try:
        result = text.format_map(_SafeDict(vars))
    except (KeyError, IndexError, ValueError):
        return text  # 格式不合法时原样保留
    if _EMPTY_SENTINEL in result:
        result = re.sub(r"\s*\x00", "", result)  # 删掉空占位符及其前导空白
        result = result.replace(_EMPTY_SENTINEL, "")  # 保险：哨兵不应残留
        result = result.strip()  # 清掉空占位符在开头/结尾留下的空格
    return result


def _format_vars(entry: FontEntry, lang: str) -> dict[str, object]:
    from core.translations import italic_label, weight_label, width_label

    vars = {
        "weight": weight_label(entry.us_weight_class, lang),
        "width": width_label(entry.us_width_class, lang),
        "italic": italic_label(entry.italic(), lang),
        "weight_num": entry.us_weight_class,
        "width_num": entry.us_width_class,
    }
    # 逐语言变量：{weight_sc} {width_sc} {italic_sc} {family_sc} {preferred_family_sc} {version_sc} ...
    # suffix = sc/tc/jp/en（与 {name_xx} 同款语言后缀）
    for l, code in NAME_TEMP_CODES.items():
        suffix = code.rsplit("_", 1)[1]
        names = entry.names[l]
        vars[code] = entry.temp_names[l]   # {name_sc}
        vars[f"weight_{suffix}"] = weight_label(entry.us_weight_class, l)
        vars[f"width_{suffix}"] = width_label(entry.us_width_class, l)
        vars[f"italic_{suffix}"] = italic_label(entry.italic(), l)
        vars[f"family_{suffix}"] = names.get(1, "")
        vars[f"subfamily_{suffix}"] = names.get(2, "")
        vars[f"preferred_family_{suffix}"] = names.get(16, "")
        vars[f"version_{suffix}"] = names.get(5, "")
    # 字符集 4 列：{charset_sc}/{charset_tc}/{charset_jp}/{charset_en}
    for l, code in CHARSET_TEMP_CODES.items():
        vars[code] = entry.charsets[l]
    return vars
