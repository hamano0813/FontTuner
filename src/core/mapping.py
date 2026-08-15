"""逻辑语言 ↔ 原始 (platformID, platEncID, langID) 记录组 的映射与转换。"""

from __future__ import annotations

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._n_a_m_e import NameRecord

from core import metadata as _metadata
from core.models import LANGS, MANAGED_NAME_IDS, FontEntry

# 四个逻辑语言 → Windows 语言 ID（langID；Windows 平台记录按 langID 识别，不挑 platEncID）
_WINDOWS_LANGID = {
    "SC": 0x0804,
    "TC": 0x0404,
    "JA": 0x0411,
    "EN": 0x0409,
}

# 默认写入组（platEncID 1 = UCS-2）：写入一律用新版本 (3,1,langID)，老字体
# 只有 platEncID 4/10 组也新建 (3,1) 写入；旧组保留供 GDI 与读取兜底
WINDOWS_LANG = {lang: (3, 1, langid) for lang, langid in _WINDOWS_LANGID.items()}

# 字体中可能存在的非 Windows 记录组 → 逻辑语言（读取 + 保存镜像用）
MAC_UNICODE_GROUP_LANG = {
    (1, 0, 0): "EN",      # Mac Roman
    (1, 25, 33): "JA",    # Mac Japanese
    (0, 3, 0): "EN",      # Unicode BMP
    (0, 4, 0): "EN",      # Unicode 全量
}

# Windows 常见 platEncID：1(UCS-2) / 4(UCS-2 旧式) / 10(Full UCS)——
# 老字体常只有 4；再加旧式非 Unicode 编码 2(ShiftJIS)/3(GBK)/5(Wansung)/6(Johab)
# 兜底读取（如 Edokan.ttc 的 (3,2) 名字记录）。Unicode 组在前、旧式在后，读取时
# Unicode 优先，旧式只填空缺；decode 兼容错标 UTF-16-BE 的字节（见 metadata/names）
_WINDOWS_ENCS = (1, 4, 10, 2, 3, 5, 6)

# 读取优先级：四个 Windows 组（各 platEncID，1 优先）在前，其次 Mac / Unicode
_READ_PRIORITY = tuple(
    (3, enc, _WINDOWS_LANGID[lang]) for lang in LANGS for enc in _WINDOWS_ENCS
) + tuple(MAC_UNICODE_GROUP_LANG)


def _group_lang(group: tuple[int, int, int]) -> str | None:
    """把原始记录组解析为逻辑语言；未映射（小语种/区域变体）返回 None。

    Windows 平台（platformID=3）按 langID 识别，platEncID 1/4/10 都算同一语言
    ——旧 TrueType 字体常以 platEncID=4 存储，只认 (3,1,*) 会读不到记录。
    """
    if group in MAC_UNICODE_GROUP_LANG:
        return MAC_UNICODE_GROUP_LANG[group]
    if group[0] == 3:
        return _LANGID_TO_LANG.get(group[2])
    return None


_LANGID_TO_LANG = {v: k for k, v in _WINDOWS_LANGID.items()}


def _all_groups_of_lang(lang: str) -> list[tuple[int, int, int]]:
    """某个逻辑语言涉及的所有记录组（Windows 各 platEncID + 可能存在的 Mac/Unicode 镜像组）。"""
    groups = [(3, enc, _WINDOWS_LANGID[lang]) for enc in _WINDOWS_ENCS]
    groups += [g for g, l in MAC_UNICODE_GROUP_LANG.items() if l == lang]
    return groups


def _windows_group(lang: str) -> tuple[int, int, int]:
    """逻辑语言的写入组：一律新版本 (3,1,langID)。

    老字体只有 platEncID 4/10 组时也新建 (3,1) 组写入——「写入一定写在新版本上」；
    旧式 (3,4)/(3,10) 组保留不删（部分老字体 GDI 依赖它们注册），读取时新组优先、
    旧组兜底，因此保存后新组数据才是权威。
    """
    return WINDOWS_LANG[lang]


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

def _format_revision(font: TTFont) -> str:
    """从 head.fontRevision 生成版本字符串（如 'Version 1.00'）；异常返回空串。"""
    try:
        rev = font["head"].fontRevision
        if rev is None:
            return ""
        return f"Version {float(rev):.2f}"
    except Exception:
        return ""


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

    # 版本号兜底：任一语言 nid5 为空时保存用此值（老字体 (3,4) 组被升级删除后，
    # 版本只留在 Mac 记录里读不到，缺 nid5 会使 Windows 预览回退读 Mac 记录而乱码）
    entry.version = next(
        (entry.names[lang][5].strip() for lang in LANGS if entry.names[lang][5].strip()),
        _format_revision(font),
    )

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
    # 版本号回退：某语言 nid 5 为空时，用字体其它语言已有的版本，否则用
    # head.fontRevision 兜底（老字体 (3,4) 组被删后版本只留在 Mac 记录里读不到，
    # 缺 nid5 会让 Windows 预览回退读 Mac 记录而乱码）
    fallback_version = next(
        (entry.names[lang][5].strip() for lang in LANGS if entry.names[lang][5].strip()),
        entry.version,
    )
    for lang in LANGS:
        if not entry.save_langs[lang]:
            continue
        # 家族名解析：首选家族(16) 空则回退到 家族名(1)；仍空则跳过该语言
        family = (entry.names[lang][16] or entry.names[lang][1]).strip()
        if not family:
            continue
        if not any(entry.names[lang][n].strip() for n in MANAGED_NAME_IDS):
            continue  # 勾选但内容全空 → 不新建

        group = _windows_group(lang)
        for name_id in MANAGED_NAME_IDS:
            # 16 一律写入家族名（含 16←1 回退），否则 prepare_metadata 会因首选家族
            # 为空而把整组记录删掉。占位符不做解析——保存只负责写入，「解析」按钮负责解析。
            value = family if name_id == 16 else entry.names[lang][name_id]
            if name_id == 5 and not str(value).strip() and fallback_version:
                value = fallback_version  # 版本号空 → 用字体已有版本
            setting[(name_id, *group)] = value

        # 镜像到字体中已有的同语言 Mac/Unicode 组（16 不可编码则整组跳过，Windows 记录为准）
        for mirror in MAC_UNICODE_GROUP_LANG:
            if mirror not in entry._raw_groups or MAC_UNICODE_GROUP_LANG[mirror] != lang:
                continue
            if not _encodable(mirror, family):
                continue
            for name_id in MANAGED_NAME_IDS:
                value = family if name_id == 16 else entry.names[lang][name_id]
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
