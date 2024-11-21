import ast
import os

import pandas as pd
from fontTools.ttLib import TTFont

from constants import FONT_WEIGHT, FONT_WIDTH


def load_metadata(font: TTFont):
    font_setting = {
        "usWeightClass": font["OS/2"].usWeightClass,
        "fsSelection": f"{font["OS/2"].fsSelection:016b}",
        "usWidthClass": font["OS/2"].usWidthClass,
    }

    lang_set = set()

    for record in font["name"].names:
        nameID = record.nameID
        platFormID = record.platformID
        platEncID = record.platEncID
        langID = record.langID

        lang_set.add((platFormID, platEncID, langID))
        try:
            font_setting[(nameID, platFormID, platEncID, langID)] = record.toUnicode()
        except UnicodeDecodeError:
            font_setting[(nameID, platFormID, platEncID, langID)] = record.toBytes()

    lang_list = list(lang_set)

    for platformID, platEncID, langID in lang_list:
        if (16, platformID, platEncID, langID) not in font_setting:
            font_setting[(16, platformID, platEncID, langID)] = ""
        if (17, platformID, platEncID, langID) not in font_setting:
            font_setting[(17, platformID, platEncID, langID)] = ""

    return font_setting


def load(font_paths: list[str]):
    metadatas = []
    for font_path in font_paths:
        if font_path.lower().endswith(".ttf") or font_path.lower().endswith(".otf"):
            font = TTFont(font_path)
            metadata = {"fontPath": font_path}
            metadata.update(load_metadata(font))
            metadatas.append(metadata)
    metadata_df = pd.DataFrame(metadatas)
    fixed_columns = metadata_df.columns[:4]
    sorted_columns = metadata_df.columns[4:]
    sorted_columns = sorted(sorted_columns, key=lambda x: (x[1], x[2], x[3], x[0]))
    new_columns = list(fixed_columns) + sorted_columns
    return metadata_df[new_columns]


def prepare_metadata(font: TTFont, font_setting: dict):
    langIDs = set()

    for key in font_setting.keys():
        if key in ("fsSelection", "usWidthClass", "usWeightClass", "fontPath"):
            continue
        _, platformID, platEncID, langID = key
        if (platformID, platEncID, langID) in langIDs:
            continue
        width = font["OS/2"].usWidthClass
        weight = font["OS/2"].usWeightClass
        if not (p_family := font_setting.get((16, platformID, platEncID, langID))):
            font["name"].removeNames(platformID=platformID, platEncID=platEncID, langID=langID)
        else:
            langIDs.add((platformID, platEncID, langID))
            if not font_setting.get((17, platformID, platEncID, langID)):
                width_str = FONT_WIDTH.get(width, ("", ""))[p_family.isascii() ^ 1]
                weight_str = FONT_WEIGHT.get(weight, ("", ""))[p_family.isascii() ^ 1]
                font_setting[(17, platformID, platEncID, langID)] = " ".join([width_str, weight_str]).strip()

    langIDs = list(langIDs)
    return langIDs


def fetch_metadata(font: TTFont, font_setting: dict, langIDs):
    weight = font["OS/2"].usWeightClass
    width = font["OS/2"].usWidthClass

    for platformID, platEncID, langID in langIDs:
        p_family = font_setting.get((16, platformID, platEncID, langID), "")
        s_family = font_setting.get((17, platformID, platEncID, langID), "")
        if s_family.isascii():
            width_str = FONT_WIDTH.get(width, ("", ""))[0] if width != 5 else ""
        else:
            width_str = FONT_WIDTH.get(width, ("", ""))[1] if width != 5 else ""
        # 1 Font Family
        if weight not in (400, 700):
            font["name"].setName(f"{p_family} {s_family}", 1, platformID, platEncID, langID)
        else:
            if width_str:
                font["name"].setName(f"{p_family} {width_str}", 1, platformID, platEncID, langID)
            else:
                font["name"].setName(p_family, 1, platformID, platEncID, langID)
        # 2 Font Subfamily
        if weight != 700:
            font["name"].setName("Regular", 2, platformID, platEncID, langID)
        else:
            font["name"].setName("Bold", 2, platformID, platEncID, langID)
        # 3 Unique ID
        unique_id = font_setting.get((3, platformID, platEncID, langID), "")
        font["name"].setName(unique_id.format(p_family, s_family, *([""] * 3)), 3, platformID, platEncID, langID)
        # 4 Full Name
        font["name"].setName(f"{p_family} {s_family}", 4, platformID, platEncID, langID)
        # 6 PostScript Name
        for pid, eid, lid in langIDs:
            p_fam = font_setting.get((16, pid, eid, lid), "")
            s_fam = font_setting.get((17, pid, eid, lid), "")
            if s_fam.isascii():
                font["name"].setName(f"{p_fam}-{s_fam}".replace(" ", "-"), 6, platformID, platEncID, langID)
                break


def save_metadata(font_setting: dict):
    font = TTFont(font_setting["fontPath"])

    weight = font_setting.get("usWeightClass", 400)
    width = font_setting.get("usWidthClass", 5)
    fs = font_setting.get("fsSelection", 64)
    mac = font["head"].macStyle

    if weight == 700:  # Bold
        fs |= 1 << 5  # Set Bold
        fs &= ~(1 << 6)  # Clear Regular
        mac |= 1 << 0  # Set Bold
    else:
        fs &= ~(1 << 5)  # Clear Bold
        mac &= ~(1 << 0)  # Clear Bold
    mac = (mac & ~(1 << 1)) | ((fs & (1 << 0)) << 1)  # Set Italic
    if width < 5:
        mac |= 1 << 5  # Set Condensed
        mac &= ~(1 << 6)  # Clear Extended
    elif width > 5:
        mac |= 1 << 6  # Set Extended
        mac &= ~(1 << 5)  # Clear Condensed
    else:
        mac &= ~((1 << 5) | (1 << 6))  # Clear Condensed and Extended

    font["OS/2"].usWeightClass = weight
    font["OS/2"].fsSelection = fs
    font["OS/2"].usWidthClass = width
    font["head"].macStyle = mac

    # for key, value in font_setting.items():
    #     if key == "usWeightClass":
    #         font["OS/2"].usWeightClass = value
    #         if value == 700:
    #             font["head"].macStyle |= 1 << 0
    #     elif key == "fsSelection":
    #         if value & (1 << 6):
    #             value &= ~0b00111111
    #             font["head"].macStyle &= ~0b00111111
    #         font["OS/2"].fsSelection = value
    #         font["head"].macStyle = (font["head"].macStyle & ~(1 << 1)) | ((value & (1 << 0)) << 1)
    #         font["head"].macStyle = (font["head"].macStyle & ~(1 << 2)) | ((value & (1 << 1)) << 1)
    #         font["head"].macStyle = (font["head"].macStyle & ~(1 << 3)) | (value & (1 << 3))
    #         font["head"].macStyle = (font["head"].macStyle & ~(1 << 0)) | ((value & (1 << 5)) >> 5)
    #     elif key == "usWidthClass":
    #         font["OS/2"].usWidthClass = value
    #         if value < 5:
    #             font["head"].macStyle |= 1 << 4
    #             font["head"].macStyle &= ~(1 << 5)
    #         elif value > 5:
    #             font["head"].macStyle |= 1 << 5
    #             font["head"].macStyle &= ~(1 << 4)
    #         else:
    #             font["head"].macStyle &= ~((1 << 4) | (1 << 5))

    langIDs = prepare_metadata(font, font_setting)
    fetch_metadata(font, font_setting, langIDs)

    for key, value in font_setting.items():
        if key in ("fsSelection", "usWidthClass", "usWeightClass", "fontPath"):
            continue
        nameID, platformID, platEncID, langID = key
        p_family = font_setting.get((16, platformID, platEncID, langID), "")
        s_family = font_setting.get((17, platformID, platEncID, langID), "")
        if nameID not in (1, 2, 3, 4, 6) and value and p_family and s_family:
            font["name"].setName(value, nameID, platformID, platEncID, langID)

    font.save(font_setting["fontPath"])


def rename_font(font_setting: dict):
    font = TTFont(font_setting["fontPath"])

    new_name = ""
    for record in font["name"].names:
        if record.nameID == 4:
            version = font_setting.get((5, record.platformID, record.platEncID, record.langID), "")
            new_name = " ".join([record.toUnicode(), version])
            s_family = font_setting.get((17, record.platformID, record.platEncID, record.langID), "")
            if not s_family.isascii():
                break

    if new_name and not os.path.exists(new_name):
        origin_path = font_setting["fontPath"]
        origin_root = os.path.dirname(origin_path)
        origin_ext = os.path.splitext(origin_path)[1]
        new_path = os.path.join(origin_root, new_name + origin_ext)
        os.rename(origin_path, new_path)


def save(dfs: list[pd.DataFrame]):
    for metadata_df in dfs:
        metadata_df.fillna("", inplace=True)
        metadata_df["fsSelection"] = metadata_df["fsSelection"].apply(lambda x: int(x, 2))
        metadata_df["usWidthClass"] = metadata_df["usWidthClass"].astype(int)
        metadata_df["usWeightClass"] = metadata_df["usWeightClass"].astype(int)

        new_columns = {col: ast.literal_eval(col) if col.startswith("(") else col for col in metadata_df.columns}
        metadata_df.rename(columns=new_columns, inplace=True)

        for _, font_setting in metadata_df.iterrows():
            save_metadata(font_setting)
            rename_font(font_setting)
