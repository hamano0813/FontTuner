"""字体元数据引擎：读取/写回字体的 name 表与 OS/2、head 表（GUI 核心引擎）。"""

from __future__ import annotations

from fontTools.ttLib import TTFont


def load_metadata(font: TTFont):
    """Load the metadata of the font and return them as a dictionary."""
    # init the font settings
    font_setting = {
        "usWeightClass": font["OS/2"].usWeightClass,
        "fsSelection": f"{font["OS/2"].fsSelection:016b}",
        "usWidthClass": font["OS/2"].usWidthClass,
        "numGlyphs" : font["maxp"].numGlyphs,
    }
    # init the set of langIDs
    langIDs = set()
    # loop through all records in the font
    for record in font["name"].names:
        # get the nameID, platformID, platEncID, and langID
        nameID = record.nameID
        platFormID = record.platformID
        platEncID = record.platEncID
        langID = record.langID
        # add the langID to the set
        langIDs.add((platFormID, platEncID, langID))
        # add the record to the font settings
        try:
            font_setting[(nameID, platFormID, platEncID, langID)] = record.toUnicode()
        except UnicodeDecodeError:
            font_setting[(nameID, platFormID, platEncID, langID)] = record.toBytes()
    # convert the set to a list
    langIDs = list(langIDs)
    # loop through all langIDs
    for platformID, platEncID, langID in langIDs:
        # add the missing records to the font settings
        if (16, platformID, platEncID, langID) not in font_setting:
            font_setting[(16, platformID, platEncID, langID)] = ""
        if (17, platformID, platEncID, langID) not in font_setting:
            font_setting[(17, platformID, platEncID, langID)] = ""
    # return the font settings
    return font_setting


def adjust_values(font: TTFont, font_setting: dict):
    """Adjust the values of the font settings and write them back to the font file."""
    # get the font style settings
    weight = font_setting.get("usWeightClass", 400)
    width = font_setting.get("usWidthClass", 5)
    fs = font_setting.get("fsSelection", 64)
    mac = font["head"].macStyle
    # adjust weight
    if weight == 700:  # Bold
        fs |= 1 << 5  # Set Bold
        fs &= ~(1 << 6)  # Clear Regular
        mac |= 1 << 0  # Set Bold
    else:  # not Bold
        fs &= ~(1 << 5)  # Clear Bold
        mac &= ~(1 << 0)  # Clear Bold
    # adjust italic
    mac = (mac & ~(1 << 1)) | ((fs & (1 << 0)) << 1)  # Set Italic
    # adjust width
    if width < 5:  # Condensed
        mac |= 1 << 5  # Set Condensed
        mac &= ~(1 << 6)  # Clear Extended
    elif width > 5:  # Extended
        mac |= 1 << 6  # Set Extended
        mac &= ~(1 << 5)  # Clear Condensed
    else:  # Normal
        mac &= ~((1 << 5) | (1 << 6))  # Clear Condensed and Extended
    # write the adjusted values back to the font
    font["OS/2"].usWeightClass = weight
    font["OS/2"].fsSelection = fs
    font["OS/2"].usWidthClass = width
    font["head"].macStyle = mac


def prepare_metadata(font: TTFont, font_setting: dict):
    """Prepare the settings for the metadata and return the langIDs without duplicates."""
    # init langIDs
    langIDs = set()
    # loop through all settings
    for key in font_setting.keys():
        # skip the fixed values
        if key in ("fsSelection", "usWidthClass", "usWeightClass", "numGlyphs", "fontPath"):
            continue
        # unpack the key
        _, platformID, platEncID, langID = key
        # skip if the langID is already in the set
        if (platformID, platEncID, langID) in langIDs:
            continue
        # get the font family
        if not (p_family := font_setting.get((16, platformID, platEncID, langID)).strip()):
            # remove all names if the font family is empty
            font["name"].removeNames(platformID=platformID, platEncID=platEncID, langID=langID)
        else:
            # add the langID to the set
            langIDs.add((platformID, platEncID, langID))
    # convert the set to a list and return it
    return list(langIDs)


def fetch_metadata(font: TTFont, font_setting: dict, langIDs):
    """Fetch the metadata from the font settings and write them back to the font file."""
    # loop through all langIDs
    for platformID, platEncID, langID in langIDs:
        # get the preferred font family and subfamily
        p_family = font_setting.get((16, platformID, platEncID, langID), "")
        s_family = font_setting.get((17, platformID, platEncID, langID), "")

        # 1 Font Family（原样写入家族名列值；留空则删除该记录，不自动生成子家族名）
        family_name = font_setting.get((1, platformID, platEncID, langID), "").strip()
        if family_name:
            font["name"].setName(family_name, 1, platformID, platEncID, langID)
        else:
            font["name"].removeNames(1, platformID, platEncID, langID)
        # 2 Font Subfamily（保存纯写入：字段有值写值，无值删记录，不自动拼 Bold/Regular）
        subfamily = font_setting.get((2, platformID, platEncID, langID), "").strip()
        if subfamily:
            font["name"].setName(subfamily, 2, platformID, platEncID, langID)
        else:
            font["name"].removeNames(2, platformID, platEncID, langID)
        # 3 Unique ID
        unique_id = font_setting.get((3, platformID, platEncID, langID), "{} {}").format(p_family, s_family, *([""] * 3)).strip()
        font["name"].setName(unique_id, 3, platformID, platEncID, langID)
        # 4 Full Name（子族名为空时只保留家族名；尾随空格会让 Windows GDI 拒绝注册该字体）
        full_name = f"{p_family} {s_family}".strip()
        font["name"].setName(full_name, 4, platformID, platEncID, langID)
        # 6 PostScript Name
        # sub loop through all langIDs
        for pid, eid, lid in langIDs:
            # get the preferred font family and subfamily for the sub loop
            p_fam = font_setting.get((16, pid, eid, lid), "")
            s_fam = font_setting.get((17, pid, eid, lid), "")
            # set the PostScript Name when the subfamily are ASCII（空家族/子家族名跳过，
            # 避免生成 "Foo-" / "-Bold" 这类畸形 PS 名）
            if p_fam and s_fam and s_fam.isascii():
                ps_name = f"{p_fam}-{s_fam}".replace(" ", "-")
                font["name"].setName(ps_name, 6, platformID, platEncID, langID)
                break


def _clean_legacy_names(font: TTFont) -> None:
    """清洗旧式 Windows 组（platEncID 4/10）记录的头尾空白。

    写入时新数据一律进 (3,1) 组、旧组不更新；但部分老字体 GDI 依赖旧组注册，
    历史坏保存可能在旧组留下尾随空格（如 nid 4 的 '和平疊圓 '），使字体无法注册。
    这里按记录自身编码（big5/cp936/cp932…）解码-去空白-回写，无法解码的原始字节
    原样保留。
    """
    name = font["name"]
    for rec in list(name.names):
        if rec.platformID != 3 or rec.platEncID not in (4, 10):
            continue
        if isinstance(rec.string, bytes):
            enc = rec.getEncoding()
            if not enc:
                continue
            try:
                text = rec.string.decode(enc)
            except UnicodeDecodeError:
                continue
            try:
                stripped = text.strip().encode(enc)
            except UnicodeEncodeError:
                continue
            if stripped != rec.string:
                rec.string = stripped
        else:
            stripped = rec.string.strip()
            if stripped != rec.string:
                rec.string = stripped


# 应用管理的四个 Windows 语言 ID（与 mapping._WINDOWS_LANGID 一致；本模块
# 不能 import mapping，避免循环依赖）
_MANAGED_LANGIDS = (0x0804, 0x0404, 0x0411, 0x0409)

# Windows cmap 旧式非 Unicode 编码 → Python codec（键是各编码的码位字节对）
_CMAP_LEGACY_CODECS = {
    2: "cp932",    # ShiftJIS 日文
    3: "cp936",    # GBK/PRC 简中
    4: "cp950",    # Big5 繁中
    5: "cp949",    # Wansung 韩文
    6: "cp1361",   # Johab 韩文
}


def _modernize_legacy_cmap(font: TTFont) -> int | None:
    """把旧式非 Unicode cmap 子表（encodingID 2/3/4/5/6）转成 (3,1) Unicode BMP。

    这些旧编码的 cmap 键是各编码的码位而非 Unicode：GDI 渲染时把 '和' 转成该编码
    的码位（如 Big5 0xA44D）再查表。Windows GDI 因此把字体当旧式中文档处理——强制
    要求对应的旧 name 记录存在且家族名含该语言汉字，纯 ASCII 名注册失败，旧编码
    字节在简体系统按 GBK 读还会乱码。这里把各编码码位解码重键为 Unicode 码位并改为
    platEncID 1，字体按现代 Unicode 处理，ASCII 名可正常显示。返回被转换的
    encodingID（无则 None）。
    """
    for table in font["cmap"].tables:
        codec = _CMAP_LEGACY_CODECS.get(table.platEncID)
        if table.platformID != 3 or codec is None:
            continue
        enc = table.platEncID
        newmap = {}
        for cp, gid in table.cmap.items():
            try:
                raw = bytes((cp,)) if cp <= 0xFF else bytes((cp >> 8, cp & 0xFF))
                ch = raw.decode(codec)
            except UnicodeDecodeError:
                continue  # 无效码位原本就是空槽，跳过
            newmap[ord(ch)] = gid
        table.platEncID = 1
        table.language = 0
        table.cmap = newmap
        return enc
    return None


def _clean_legacy_mac_names(font: TTFont) -> None:
    """删除旧式 Mac 中文名字记录（langID 0x13 且含非 ASCII 内容）。

    1999 年前后的字体把 Big5 字节塞进 Mac Roman 记录（Mac 预览乱码）或作为旧中文名，
    Windows 字体预览读这些记录会显示乱码。现代字体的 Mac 记录用 langID 0（英文），
    不受影响。保留版权/子家族/版本/商标（nid 0/2/5/7）等 ASCII 元数据。
    """
    name = font["name"]
    for rec in list(name.names):
        if rec.platformID != 1 or rec.langID != 0x13 or rec.nameID not in (1, 3, 4, 6):
            continue
        try:
            has_high = any(ord(c) > 0x7F for c in rec.toUnicode())
        except UnicodeDecodeError:
            has_high = True
        if has_high:
            name.removeNames(rec.nameID, rec.platformID, rec.platEncID, rec.langID)


def apply_font_settings(font: TTFont, font_setting: dict, remove_groups=()):
    """Apply the settings to an already-open font object (does not open or save).

    remove_groups: iterable of (platformID, platEncID, langID) — 删除这些记录组的全部
    name 记录（未勾选语言的删除语义）。
    """
    # remove the records of the unchecked languages
    for platformID, platEncID, langID in remove_groups:
        font["name"].removeNames(platformID=platformID, platEncID=platEncID, langID=langID)
    # 现代化旧式非 Unicode cmap → (3,1)；转换后对应的旧 name 记录不再被 GDI 需要，
    # 删除原本的过时信息（旧编码字节在简体系统按 GBK 读会乱码、纯 ASCII 名会被拒）
    legacy_enc = _modernize_legacy_cmap(font)
    if legacy_enc is not None:
        for langID in _MANAGED_LANGIDS:
            font["name"].removeNames(platformID=3, platEncID=legacy_enc, langID=langID)
    # 删除旧式 Mac 中文名字记录（Big5 乱码 / 旧名），无论 cmap 是否已升级都要清
    _clean_legacy_mac_names(font)
    # adjust the values
    adjust_values(font, font_setting)
    # 清洗旧式 Windows 组记录的头尾空白（(3,10) 等未被删除的旧组）
    _clean_legacy_names(font)
    # prepare the metadata
    langIDs = prepare_metadata(font, font_setting)
    # fetch the metadata
    fetch_metadata(font, font_setting, langIDs)
    # loop through all settings
    for key, value in font_setting.items():
        # skip the fixed values
        if key in ("fsSelection", "usWidthClass", "usWeightClass", "numGlyphs", "fontPath"):
            continue
        # unpack the key
        nameID, platformID, platEncID, langID = key
        # get the preferred font family and subfamily
        p_family = font_setting.get((16, platformID, platEncID, langID), "")
        s_family = font_setting.get((17, platformID, platEncID, langID), "")
        # set the normal name when preferred font family and subfamily are not empty
        if nameID not in (1, 2, 3, 4, 6) and p_family and s_family:
            if value:
                font["name"].setName(value, nameID, platformID, platEncID, langID)
            else:
                font["name"].removeNames(nameID, platformID, platEncID, langID)


def save_metadata(font_setting: dict, font: TTFont | None = None, remove_groups=()):
    """Save the metadata of the font setting and write them back to the font file."""
    # load the font if not given（自己打开的要负责关闭，否则句柄锁住文件）
    if font is None:
        font = TTFont(font_setting["fontPath"])
        own_font = True
    else:
        own_font = False
    try:
        # apply the settings
        apply_font_settings(font, font_setting, remove_groups)
        # save the font
        font.save(font_setting["fontPath"])
        return True
    except PermissionError as e:
        print(f"Failed to save {font_setting['fontPath']}. Permission denied.")
        return False
    finally:
        if own_font:
            try:
                font.close()
            except Exception:
                pass
