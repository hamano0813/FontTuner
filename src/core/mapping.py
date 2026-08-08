"""逻辑语言 ↔ 原始 (platformID, platEncID, langID) 记录组 的映射与转换。"""

from __future__ import annotations

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._n_a_m_e import NameRecord

from core import metadata as _metadata
from core.models import LANGS, MANAGED_NAME_IDS, FontEntry
from core.templates import format_name

# 四个逻辑语言 → Windows 主记录组
WINDOWS_LANG = {
    "SC": (3, 1, 0x0804),
    "TC": (3, 1, 0x0404),
    "JA": (3, 1, 0x0411),
    "EN": (3, 1, 0x0409),
}

# 字体中可能存在的非 Windows 记录组 → 逻辑语言（读取 + 保存镜像用）
MAC_UNICODE_GROUP_LANG = {
    (1, 0, 0): "EN",      # Mac Roman
    (1, 25, 33): "JA",    # Mac Japanese
    (0, 3, 0): "EN",      # Unicode BMP
    (0, 4, 0): "EN",      # Unicode 全量
}

# 读取优先级：四个 Windows 组优先，其次 Mac / Unicode
_READ_PRIORITY = tuple(WINDOWS_LANG[lang] for lang in LANGS) + tuple(MAC_UNICODE_GROUP_LANG)


def _group_lang(group: tuple[int, int, int]) -> str | None:
    """把原始记录组解析为逻辑语言；未映射（小语种/区域变体）返回 None。"""
    if group in MAC_UNICODE_GROUP_LANG:
        return MAC_UNICODE_GROUP_LANG[group]
    for lang, g in WINDOWS_LANG.items():
        if g == group:
            return lang
    return None


def _all_groups_of_lang(lang: str) -> list[tuple[int, int, int]]:
    """某个逻辑语言涉及的所有记录组（Windows 主组 + 可能存在的 Mac/Unicode 镜像组）。"""
    groups = [WINDOWS_LANG[lang]]
    groups += [g for g, l in MAC_UNICODE_GROUP_LANG.items() if l == lang]
    return groups


def _encodable(group: tuple[int, int, int], value: str) -> bool:
    """判断字符串能否以该记录组的平台编码表示（如 mac_roman 不能存中文）。"""
    if not value:
        return True
    record = NameRecord()
    record.platformID, record.platEncID, record.langID = group
    record.string = value
    try:
        record.toBytes()
        return True
    except UnicodeEncodeError:
        return False


# ---------------------------------------------------------------- 读取

def read_entry(font_path: str, font_index: int, font: TTFont) -> FontEntry:
    """从已打开的 TTFont 读取一个子字体的逻辑字段。"""
    raw = _metadata.load_metadata(font)
    entry = FontEntry(font_path=font_path, font_index=font_index)
    entry.us_weight_class = int(raw["usWeightClass"])
    entry.us_width_class = int(raw["usWidthClass"])
    entry.fs_selection = int(raw["fsSelection"], 2)
    entry.num_glyphs = int(raw["numGlyphs"])
    entry._raw_groups = {
        key[1:] for key in raw if isinstance(key, tuple) and len(key) == 4
    }

    # 按优先级填充每组字段，Windows 记录优先（仅当目标字段仍为空）
    for group in _READ_PRIORITY:
        lang = _group_lang(group)
        if lang is None or group not in entry._raw_groups:
            continue
        for name_id in MANAGED_NAME_IDS:
            val = raw.get((name_id, *group), "")
            if val and not entry.names[lang][name_id]:
                entry.names[lang][name_id] = val

    # 默认保存勾选 = 该语言有数据
    for lang in LANGS:
        entry.save_langs[lang] = any(
            entry.names[lang][n].strip() for n in MANAGED_NAME_IDS
        )
        # 临时名称列初始化为该语言的家族名（16 优先，回退 1），供 {name_*} 占位符引用
        entry.temp_names[lang] = entry.names[lang][16] or entry.names[lang][1]
    return entry


# ---------------------------------------------------------------- 保存

def build_font_setting(entry: FontEntry) -> dict:
    """把逻辑字段映射为原始 (nameID, *group) 键控 dict，供保存引擎消费。

    仅包含「勾选且有内容」的语言：勾选但全空不新建；未勾选不参与（由
    compute_remove_groups 负责删除）。
    """
    setting = {
        "fontPath": entry.font_path,
        "usWeightClass": entry.us_weight_class,
        "usWidthClass": entry.us_width_class,
        "fsSelection": entry.fs_selection,
        "numGlyphs": entry.num_glyphs,
    }
    for lang in LANGS:
        if not entry.save_langs[lang]:
            continue
        # 家族名解析：首选家族(16) 空则回退到 家族名(1)；仍空则跳过该语言
        family = (entry.names[lang][16] or entry.names[lang][1]).strip()
        if not family:
            continue
        if not any(entry.names[lang][n].strip() for n in MANAGED_NAME_IDS):
            continue  # 勾选但内容全空 → 不新建

        group = WINDOWS_LANG[lang]
        for name_id in MANAGED_NAME_IDS:
            # 16 一律写入解析后的家族名（含 16←1 回退），否则 prepare_metadata 会因
            # 首选家族为空而把整组记录删掉
            value = family if name_id == 16 else entry.names[lang][name_id]
            if "{" in value:
                value = format_name(value, entry, lang)
            setting[(name_id, *group)] = value

        # 镜像到字体中已有的同语言 Mac/Unicode 组（16 不可编码则整组跳过，Windows 记录为准）
        for mirror in MAC_UNICODE_GROUP_LANG:
            if mirror not in entry._raw_groups or MAC_UNICODE_GROUP_LANG[mirror] != lang:
                continue
            if not _encodable(mirror, family):
                continue
            for name_id in MANAGED_NAME_IDS:
                value = entry.names[lang][name_id]
                if name_id == 16:
                    value = family
                if "{" in value:
                    value = format_name(value, entry, lang)
                if name_id in (16, 17) or _encodable(mirror, value):
                    setting[(name_id, *mirror)] = value
    return setting


def compute_remove_groups(entry: FontEntry) -> list[tuple[int, int, int]]:
    """未勾选且字体中确实存在的记录组 → 保存时删除。小语种/区域变体永不在其中。"""
    groups = []
    for lang in LANGS:
        if entry.save_langs[lang]:
            continue
        for g in _all_groups_of_lang(lang):
            if g in entry._raw_groups:
                groups.append(g)
    return groups


def deleted_langs(entry: FontEntry) -> list[str]:
    """保存时将被删除的逻辑语言（用于保存前确认提示）。"""
    return [
        lang for lang in LANGS
        if not entry.save_langs[lang]
        and any(g in entry._raw_groups for g in _all_groups_of_lang(lang))
    ]


def unsavable_langs(entry: FontEntry) -> list[str]:
    """勾选了、有内容、但因缺少家族名而无法写入的逻辑语言（保存前提示）。"""
    return [
        lang for lang in LANGS
        if entry.save_langs[lang]
        and not (entry.names[lang][16] or entry.names[lang][1]).strip()
        and any(entry.names[lang][n].strip() for n in MANAGED_NAME_IDS)
    ]
