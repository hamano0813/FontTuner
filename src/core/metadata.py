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
        unique_id = font_setting.get((3, platformID, platEncID, langID), "{} {}").format(p_family, s_family, *([""] * 3))
        font["name"].setName(unique_id, 3, platformID, platEncID, langID)
        # 4 Full Name
        full_name = f"{p_family} {s_family}"
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


def apply_font_settings(font: TTFont, font_setting: dict, remove_groups=()):
    """Apply the settings to an already-open font object (does not open or save).

    remove_groups: iterable of (platformID, platEncID, langID) — 删除这些记录组的全部
    name 记录（未勾选语言的删除语义）。
    """
    # remove the records of the unchecked languages
    for platformID, platEncID, langID in remove_groups:
        font["name"].removeNames(platformID=platformID, platEncID=platEncID, langID=langID)
    # adjust the values
    adjust_values(font, font_setting)
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
