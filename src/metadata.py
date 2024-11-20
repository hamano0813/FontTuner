import ast
import os

import pandas as pd
from fontTools.ttLib import TTFont

from weight import FONT_WEIGHT


def load_metadata(font: TTFont):
    font_setting = {
        "fsSelection": font["OS/2"].fsSelection,
        "usWeightClass": font["OS/2"].usWeightClass,
    }

    lang_set = set()

    for record in font["name"].names:
        if record.nameID not in (1, 2, 3, 4, 5, 6, 7, 16, 17):
            continue

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
    fixed_columns = metadata_df.columns[:3]
    sorted_columns = metadata_df.columns[3:]
    sorted_columns = sorted(sorted_columns, key=lambda x: (x[1], x[2], x[3], x[0]))
    new_columns = list(fixed_columns) + sorted_columns
    return metadata_df[new_columns]


def prepare_metadata(font: TTFont, font_setting: dict):
    langIDs = set()

    for key in font_setting.keys():
        if key in ("fsSelection", "usWeightClass", "fontPath"):
            continue
        nameID, platformID, platEncID, langID = key
        if nameID == 16:
            if not (p_family := font_setting.get((16, platformID, platEncID, langID), "")):
                font["name"].removeNames(platformID=platformID, platEncID=platEncID, langID=langID)
            else:
                langIDs.add((platformID, platEncID, langID))
                if not font_setting.get((17, platformID, platEncID, langID), ""):
                    weight = font["OS/2"].usWeightClass
                    if p_family.isascii():
                        font_setting[(17, platformID, platEncID, langID)] = FONT_WEIGHT.get(weight, ("", ""))[0]
                    else:
                        font_setting[(17, platformID, platEncID, langID)] = FONT_WEIGHT.get(weight, ("", ""))[1]

    langIDs = list(langIDs)
    return langIDs


def save_metadata(font_setting: dict):
    font = TTFont(font_setting["fontPath"])
    for key, value in font_setting.items():
        if key == "fsSelection":
            font["OS/2"].fsSelection = value
        elif key == "usWeightClass":
            font["OS/2"].usWeightClass = value

    langIDs = prepare_metadata(font, font_setting)

    for key, value in font_setting.items():
        if key in ("fsSelection", "usWeightClass", "fontPath"):
            continue
        nameID, platformID, platEncID, langID = key
        p_family = font_setting.get((16, platformID, platEncID, langID), "")
        s_family = font_setting.get((17, platformID, platEncID, langID), "")
        if not all((p_family, s_family)):
            continue
        # Font Family
        if nameID == 1:
            if font["OS/2"].usWeightClass not in (400, 700):
                font["name"].setName(f"{p_family} {s_family}", nameID, platformID, platEncID, langID)
            else:
                font["name"].setName(p_family, nameID, platformID, platEncID, langID)
        # Font Subfamily
        elif nameID == 2:
            if font["OS/2"].usWeightClass != 700:
                font["name"].setName("Regular", nameID, platformID, platEncID, langID)
            else:
                font["name"].setName("Bold", nameID, platformID, platEncID, langID)
        # Unique ID
        elif nameID == 3:
            unique_id = font_setting.get((nameID, platformID, platEncID, langID), "")
            font["name"].setName(unique_id.format(p_family, s_family, *([""] * 10)), nameID, platformID, platEncID, langID)
        # Full Name
        elif nameID == 4:
            font["name"].setName(f"{p_family} {s_family}", nameID, platformID, platEncID, langID)
        # PostScript Name
        elif nameID == 6:
            for pid, eid, lid in langIDs:
                p_fam = font_setting.get((16, pid, eid, lid), "")
                s_fam = font_setting.get((17, pid, eid, lid), "")
                if all((p_fam, s_fam)) and s_fam.isascii():
                    font["name"].setName(f"{p_fam}-{s_fam}".replace(" ", "-"), nameID, platformID, platEncID, langID)
                    break
        elif nameID not in (1, 2, 3, 4, 6) and value:
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
        metadata_df["fsSelection"] = metadata_df["fsSelection"].astype(int)
        metadata_df["usWeightClass"] = metadata_df["usWeightClass"].astype(int)

        new_columns = {col: ast.literal_eval(col) if col.startswith("(") else col for col in metadata_df.columns}
        metadata_df.rename(columns=new_columns, inplace=True)

        for _, font_setting in metadata_df.iterrows():
            save_metadata(font_setting)
            rename_font(font_setting)
