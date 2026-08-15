"""name 表 struct 直读：不依赖 fontTools，直接解析字体二进制拿名称字段。

返回的字段供字体管理树各列展示（family/subfamily/sub_name/win_name/en_name/version/glyphs），
由 cache.py 按 size+mtime 增量缓存复用。
"""

from __future__ import annotations

import struct

# 语言键优先级：简 > 英 > 日 > 繁（「Windows 标准字体名」列默认取用顺序）
_LANG_PRIORITY = ("sc", "en", "jp", "tc")


def _win_lang_key(lang_id: int) -> str | None:
    """Windows 平台语言 ID → 简/繁/日/英 键（中文主语言 0x04 再按子语言细分）。"""
    primary = lang_id & 0x3FF
    if primary == 0x09:      # English（en-US/en-GB/…）
        return "en"
    if primary == 0x11:      # Japanese
        return "jp"
    if primary == 0x04:      # Chinese：子语言 2/3 简体，1/4/5 繁体
        return "sc" if (lang_id >> 10) & 0x3F in (2, 3) else "tc"
    return None


def _mac_lang_key(lang_id: int) -> str | None:
    """Mac 平台语言 ID → 键（仅收录简/繁/日/英，其余返回 None）。"""
    return {0: "en", 11: "jp", 19: "tc", 33: "sc"}.get(lang_id)


_MAC_CODECS = {
    0: "mac_roman", 1: "mac_japanese", 2: "mac_tradchinese", 25: "mac_simpchinese",
    3: "mac_korean", 7: "mac_cyrillic", 21: "mac_thai", 4: "mac_arabic", 5: "mac_hebrew",
}

# Windows 旧式非 Unicode 编码 → codec（(3,2)ShiftJIS/(3,3)GBK/(3,4)Big5/(3,5)Wansung/(3,6)Johab）
_LEGACY_WIN_CODECS = {2: "cp932", 3: "cp936", 4: "cp950", 5: "cp949", 6: "cp1361"}


def _looks_utf16_mojibake(text: str) -> bool:
    """名义编码解出的文本是否明显是错标的 UTF-16-BE 字节。

    老字体常把 platEncID 标成旧式编码、实际字节却是 UTF-16-BE（如 Edokan.ttc 的
    (3,2) 记录）。UTF-16-BE 字节按 ShiftJIS/Big5 等解码会混出半角假名或嵌控制符，
    据此判定后回退按 UTF-16-BE 重解。
    """
    if any(0xFF61 <= ord(c) <= 0xFF9F for c in text):  # 半角假名区（正常名字里基本没有）
        return True
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in text):  # NUL 等控制符
        return True
    return False


def _decode_name_raw(platform: int, enc: int, raw: bytes) -> str:
    """按平台/编码解码 name 记录文本。

    Mac(1) 用对应 mac_* 编码（CJK 记录须 mac_japanese/simpchinese 等，mac_roman 会乱码）；
    Windows(3)/Unicode(0) 为 UTF-16（平台 0 enc 4 为小端）。
    旧式 Windows 编码（enc 2/3/4/5/6）先按名义编码解，结果明显是错标的 UTF-16-BE
    （半角假名/控制符）时回退按 UTF-16-BE 解。
    """
    if platform == 1:
        try:
            return raw.decode(_MAC_CODECS.get(enc, "mac_roman"))
        except (UnicodeDecodeError, LookupError):
            return raw.decode("latin-1", "replace")
    codec = _LEGACY_WIN_CODECS.get(enc)
    if platform == 3 and codec is not None:
        try:
            nominal = raw.decode(codec)
        except (UnicodeDecodeError, LookupError):
            nominal = None
        if nominal is not None and not _looks_utf16_mojibake(nominal):
            return nominal
        try:
            return raw.decode("utf-16-be")
        except UnicodeDecodeError:
            return nominal or raw.decode("latin-1", "replace")
    return raw.decode("utf-16-le" if platform == 0 and enc == 4 else "utf-16-be")


def _read_name_table(path: str, face_index: int = 0) -> tuple[str, str, str, str, str, str, int]:
    """struct 直读 name 表 + maxp 表，返回 (family, subfamily, sub_name, win_name, en_name, version, glyphs)。

    family    — 原逻辑第一匹配（nameID 16→1 × 平台 3→0→1），供注册表/用户字体匹配；
    subfamily — 同逻辑取子家族名（nameID 17→2），供 TTC face 展示 / 安装命名；
    sub_name  — 本地化子家族名：与 win_name 同语言的子家族名（nameID 17→2），
                供字体管理树「子家族名」列与 Windows 标准字体名同语言展示，缺则回退 subfamily；
    win_name  — Windows 标准字体名列展示名：按 简→英→日→繁 优先级取同语言
                家族名(nameID 1)，同语言缺则回退首选家族名(nameID 16)；
                全缺回退 family；
    en_name   — 英文家族名（语言 en，nameID 16→1），作下拉框隐藏匹配词，无则回退 family；
    version   — 版本字符串（nameID 5）：按 英→简→日→繁 优先级取同语言版本串，
                截断到首个分号（去掉厂商/字体工具尾巴）；全缺为空；
    glyphs    — 字形数（maxp 表 numGlyphs），读取失败为 0。
    TTC 取第 face_index 个子字体（默认 0）；失败返回 ("", "", "", "", "", "", 0)。
    """
    try:
        with open(path, "rb") as f:
            magic = f.read(4)
            base = 0
            if magic == b"ttcf":
                f.read(4)  # version
                num_fonts = struct.unpack(">I", f.read(4))[0]
                if face_index < 0 or face_index >= num_fonts:
                    return "", "", "", "", "", "", 0
                # 'ttcf'(4) + version(4) + numFonts(4) 之后是 numFonts 个 32 位子字体偏移
                f.seek(12 + 4 * face_index)
                base = struct.unpack(">I", f.read(4))[0]
                f.seek(base)
                magic = f.read(4)
            if magic not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
                return "", "", "", "", "", "", 0
            header = f.read(8)  # numTables/searchRange/entrySelector/rangeShift
            if len(header) < 8:
                return "", "", "", "", "", "", 0
            num_tables = struct.unpack(">H", header[0:2])[0]
            name_off = name_len = maxp_off = None
            for _ in range(num_tables):
                rec = f.read(16)
                if len(rec) < 16:
                    return "", "", "", "", "", "", 0
                tag = rec[0:4]
                offset, length = struct.unpack(">II", rec[8:16])
                if tag == b"name":
                    name_off, name_len = offset, length
                elif tag == b"maxp":
                    maxp_off = offset
            if name_off is None:
                return "", "", "", "", "", "", 0
            # TTC 子字体的表偏移是绝对文件偏移（实测 fontTools 与 Windows 字体均如此），
            # base 只用于定位 sfnt 头，读表数据直接用 name_off / maxp_off
            f.seek(name_off)
            data = f.read(name_len)
            if len(data) < 6:
                return "", "", "", "", "", "", 0
            # 字形数：maxp 表 offset 4 处的 2 字节 numGlyphs（TTF/OTF 均为此布局）
            glyphs = 0
            if maxp_off is not None:
                f.seek(maxp_off)
                maxp = f.read(6)
                if len(maxp) >= 6:
                    glyphs = struct.unpack(">H", maxp[4:6])[0]
            count = struct.unpack(">H", data[2:4])[0]
            string_offset = struct.unpack(">H", data[4:6])[0]
            records = []
            for i in range(count):
                rec = data[6 + i * 12: 6 + (i + 1) * 12]
                if len(rec) < 12:
                    break
                platform, enc, lang_id, nid, length, off = struct.unpack(">HHHHHH", rec)
                records.append((platform, enc, lang_id, nid, length, off))
    except (OSError, struct.error):
        return "", "", "", "", "", "", 0

    texts: dict[tuple, str] = {}   # (platform, lang_id, nid) -> 首个文本
    ordered: list[tuple] = []      # 首次出现顺序
    for platform, enc, lang_id, nid, length, off in records:
        if nid not in (1, 2, 5, 16, 17):  # 5=版本字符串，也参与语言分桶
            continue
        raw = data[string_offset + off: string_offset + off + length]
        if len(raw) < length:
            continue
        try:
            text = _decode_name_raw(platform, enc, raw).strip()
        except (UnicodeDecodeError, LookupError):
            continue
        if not text:
            continue
        key = (platform, lang_id, nid)
        if key not in texts:
            texts[key] = text
            ordered.append(key)

    def _first_match(*nids: int) -> str:
        """原逻辑第一匹配（nameID 优先级 × 平台 3→0→1，文件内首个）。"""
        for nid in nids:
            for platform in (3, 0, 1):
                for plat, lang_id, nid2 in ordered:
                    if plat == platform and nid2 == nid:
                        return texts[(plat, lang_id, nid2)]
        return ""

    family = _first_match(16, 1)
    subfamily = _first_match(17, 2)

    # 按语言收集：best_1=家族名(1)，best_2=子家族名(2)，best_16=首选家族名(16)，
    # best_17=首选子家族名(17)，best_5=版本串(5)。
    # 同语言多平台记录时优先 Windows(3)，其次 Mac(1)/Unicode(0) 兜底，
    # 避免 Mac 记录（尤其 CJK 编码差异）覆盖 Windows 的干净文本。
    _plat_priority = {3: 0, 1: 1, 0: 2}
    _buckets: dict[int, dict[str, tuple[int, str]]] = {1: {}, 2: {}, 5: {}, 16: {}, 17: {}}
    for platform, lang_id, nid in ordered:
        if nid not in _buckets:
            continue
        lk = _win_lang_key(lang_id) if platform == 3 else (
            _mac_lang_key(lang_id) if platform == 1 else None)
        if lk is None:
            continue
        bucket = _buckets[nid]
        cur = bucket.get(lk)
        if cur is None or _plat_priority[platform] < cur[0]:
            bucket[lk] = (_plat_priority[platform], texts[(platform, lang_id, nid)])
    best_1 = {k: v[1] for k, v in _buckets[1].items()}
    best_2 = {k: v[1] for k, v in _buckets[2].items()}
    best_5 = {k: v[1] for k, v in _buckets[5].items()}
    best_16 = {k: v[1] for k, v in _buckets[16].items()}
    best_17 = {k: v[1] for k, v in _buckets[17].items()}

    # version：版本字符串按 英→简→日→繁 优先级取（与 win_name 的 简→英→日→繁 不同），
    # 截断到首个分号去掉厂商/字体工具尾巴（如 "Version 2.00;FontCreator 11.5..."）
    version = ""
    for lk in ("en", "sc", "jp", "tc"):
        if lk in best_5:
            version = best_5[lk].split(";", 1)[0].strip()
            break

    # win_name：简→英→日→繁，取同语言家族名(nameID 1)，缺则回退首选家族名(nameID 16)
    win_name = ""
    win_lang = None
    for lk in _LANG_PRIORITY:
        if lk in best_1:
            win_name, win_lang = best_1[lk], lk
            break
        if lk in best_16:
            win_name, win_lang = best_16[lk], lk
            break
    if not win_name:  # 回退：文件里第一个家族名
        win_name = family

    # sub_name：与 win_name 同语言的子家族名（首选子家族名 17 → 子家族名 2），
    # 与「Windows 标准字体名」列同语言展示；同语言缺则回退 subfamily（首个匹配）
    sub_name = ""
    if win_lang is not None:
        sub_name = best_17.get(win_lang) or best_2.get(win_lang) or ""
    if not sub_name:
        sub_name = subfamily

    # en_name：英文家族名（语言 en，nameID 16→1），作下拉框隐藏匹配词；无则回退 family
    en_name = best_16.get("en") or best_1.get("en") or ""
    if not en_name:
        en_name = family
    return family, subfamily, sub_name, win_name, en_name, version, glyphs
