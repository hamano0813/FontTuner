"""信息模板：字段集 + 字重/字宽/斜体映射表 + JSON 持久化 + 一键应用。

字重/字宽/斜体的文本全部由各模板的映射表定义（weight_map/width_map/italic_map），
编辑器「模板」列记录应用了哪个模板；解析占位符 {weight_sc} 等时按名查表取文本。
保存不解析占位符、不自动生成子家族名——解析归「解析」按钮，保存纯写入。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field

from core.models import CHARSET_TEMP_CODES, LANGS, NAME_TEMP_CODES, FontEntry
from core.paths import TEMPLATES_PATH

# 模板可设置的字段：全部 name 字段（含子家族名 2，可填 {width_sc} {weight_sc} 等占位符）
TEMPLATE_NAME_IDS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 256, 257, 258]

# 映射种类 → 值键类型（加载时还原）
_MAP_TYPES = {"weight": int, "width": int, "italic": bool}


@dataclass
class VendorTemplate:
    name: str
    field_values: dict[str, dict[int, str]] = field(default_factory=dict)
    # lang_key("ALL"/"SC"/"TC"/"JA"/"EN") -> {nameID: value}
    weight_map: dict[int, dict[str, str]] = field(default_factory=dict)
    # {字重值: {语言: 文本}}，不定长
    width_map: dict[int, dict[str, str]] = field(default_factory=dict)
    # {字宽值: {语言: 文本}}，固定 9 档
    italic_map: dict[bool, dict[str, str]] = field(default_factory=dict)
    # {斜体: {语言: 文本}}，固定 2 档
    rename_template: str = ""   # 重命名模板（含 {占位符}；空=应用时不重命名）


def _restore_key(value, ktype: type) -> int | bool:
    return str(value).lower() == "true" if ktype is bool else int(value)


def _migrate_translations(translations_data: dict) -> dict:
    """旧 {lang: {kind: {value: label}}} → 新 {kind: {value: {lang: label}}}。"""
    out: dict[str, dict] = {kind: {} for kind in _MAP_TYPES}
    for lang, kinds in translations_data.items():
        if lang not in LANGS:
            continue
        for kind, values in kinds.items():
            if kind not in _MAP_TYPES:
                continue
            for value, label in values.items():
                v = _restore_key(value, _MAP_TYPES[kind])
                out[kind].setdefault(v, {})[lang] = label
    return out


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
        item = dict(item)
        # JSON 对象键恒为字符串，nameID 键需还原为 int
        item["field_values"] = {
            lang: {int(nid): text for nid, text in values.items()}
            for lang, values in item.get("field_values", {}).items()
        }
        # 新结构 weight_map/width_map/italic_map（{值: {语言: 文本}}）
        migrated = {}
        for kind, ktype in _MAP_TYPES.items():
            raw = item.get(kind + "_map")
            if isinstance(raw, dict):
                item[kind + "_map"] = {
                    _restore_key(v, ktype): {lng: t for lng, t in vals.items()}
                    for v, vals in raw.items()
                }
        # 旧结构 translations 迁移到三 map（新 map 为空时采用）
        old_trans = item.pop("translations", None)
        if old_trans:
            migrated = _migrate_translations(old_trans)
            for kind in _MAP_TYPES:
                if not item.get(kind + "_map"):
                    item[kind + "_map"] = migrated.get(kind, {})
        templates.append(VendorTemplate(**item))
    return templates


def save_templates(templates: list[VendorTemplate], path: str | None = None) -> None:
    path = path or TEMPLATES_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(t) for t in templates], f, ensure_ascii=False, indent=2)
    invalidate_template_cache()


# ---------------------------------------------------------------- 模板查表（解析用）

_template_cache: dict[str, VendorTemplate] | None = None


def _load_template_cache() -> dict[str, VendorTemplate]:
    global _template_cache
    if _template_cache is None:
        _template_cache = {t.name: t for t in load_templates()}
    return _template_cache


def invalidate_template_cache() -> None:
    """模板保存/删除后调用，使解析查表用上最新映射。"""
    global _template_cache
    _template_cache = None


def template_label(template_name: str, kind: str, value, lang: str) -> str:
    """从指定模板的映射表取文本；模板/语言/值任一缺失返回空串。"""
    if not template_name or not lang:
        return ""
    tmpl = _load_template_cache().get(template_name)
    if tmpl is None:
        return ""
    mp = {"weight": tmpl.weight_map, "width": tmpl.width_map,
          "italic": tmpl.italic_map}.get(kind)
    if not mp:
        return ""
    langs = mp.get(value)
    if not langs:
        return ""
    return (langs.get(lang) or "").strip()


# ---------------------------------------------------------------- 应用

def apply_template(entry: FontEntry, tmpl: VendorTemplate) -> None:
    """把模板字段应用到单个字体，并自动勾选受影响语言的保存开关。

    记录 entry.template_name 供解析时按模板查字重/字宽/斜体文本；模板字段（含
    子家族名 2）原样写入、含 `{...}` 占位符不展开，留给「解析」按钮；模板中为
    空的字段不覆盖，保留字体原有值。
    """
    entry.template_name = tmpl.name
    all_values = tmpl.field_values.get("ALL", {})
    for lang in LANGS:
        values = dict(all_values)
        values.update(tmpl.field_values.get(lang, {}))
        if not values:
            continue
        for name_id, text in values.items():
            if not text or not text.strip():
                continue  # 模板字段为空 → 跳过，保留字体原有值
            entry.names[lang][name_id] = text
            entry.save_langs[lang] = True  # 模板可新建该语言记录
    # 重命名模板：模板内为空则写空（不重命名），非空则填入占位符模板
    entry.rename_template = tmpl.rename_template or ""


def resolve_entry_placeholders(entry: FontEntry, langs: tuple = LANGS) -> int:
    """把 entry 各语言 name 字段中的 `{占位符}` 就地解析为正常文本。

    保存不解析；此函数由「解析」按钮调用，让用户提前看到最终文本。无占位符的
    字段跳过。返回解析的字段数。
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


def _entry_label(entry: FontEntry, kind: str, value, lang: str) -> str:
    """按 entry.template_name 查模板映射表取文本（无模板/缺失返回空）。"""
    return template_label(entry.template_name, kind, value, lang)


def _format_vars(entry: FontEntry, lang: str) -> dict[str, object]:
    vars = {
        "weight": _entry_label(entry, "weight", entry.us_weight_class, lang),
        "width": _entry_label(entry, "width", entry.us_width_class, lang),
        "italic": _entry_label(entry, "italic", entry.italic(), lang),
        "weight_num": entry.us_weight_class,
        "width_num": entry.us_width_class,
    }
    # 逐语言变量：{weight_sc} {width_sc} {italic_sc} {family_sc} {preferred_family_sc} {version_sc} ...
    # suffix = sc/tc/jp/en（与 {name_xx} 同款语言后缀）
    for l, code in NAME_TEMP_CODES.items():
        suffix = code.rsplit("_", 1)[1]
        names = entry.names[l]
        vars[code] = entry.temp_names[l]   # {name_sc}
        vars[f"weight_{suffix}"] = _entry_label(entry, "weight", entry.us_weight_class, l)
        vars[f"width_{suffix}"] = _entry_label(entry, "width", entry.us_width_class, l)
        vars[f"italic_{suffix}"] = _entry_label(entry, "italic", entry.italic(), l)
        vars[f"family_{suffix}"] = names.get(1, "")
        vars[f"subfamily_{suffix}"] = names.get(2, "")
        vars[f"preferred_family_{suffix}"] = names.get(16, "")
        vars[f"version_{suffix}"] = names.get(5, "")
    # 字符集 4 列：{charset_sc}/{charset_tc}/{charset_jp}/{charset_en}
    for l, code in CHARSET_TEMP_CODES.items():
        vars[code] = entry.charsets[l]
    return vars
