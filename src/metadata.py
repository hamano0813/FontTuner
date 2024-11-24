import ast
import os

import pandas as pd
from fontTools.ttLib import TTFont

from constants import FONT_STYLE, FONT_WEIGHT, FONT_WIDTH


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


def load(font_paths: list[str]):
    """Load the metadata of the fonts and return them as a DataFrame."""
    # init the list of metadata
    metadatas = []
    # loop through all font paths
    for font_path in font_paths:
        # check if the font is a TrueType or OpenType font
        if font_path.lower().endswith(".ttf") or font_path.lower().endswith(".otf"):
            # load the font and get the metadata
            font = TTFont(font_path)
            metadata = {"fontPath": font_path}
            metadata.update(load_metadata(font))
            metadatas.append(metadata)
    # return the metadata as a DataFrame
    metadata_df = pd.DataFrame(metadatas)
    # sort the columns
    fixed_columns = metadata_df.columns[:5]
    sorted_columns = metadata_df.columns[5:]
    sorted_columns = sorted(sorted_columns, key=lambda x: (x[1], x[2], x[3], x[0]))
    new_columns = list(fixed_columns) + sorted_columns
    # return the sorted DataFrame
    return metadata_df[new_columns]


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
            # get font style settings
            weight = font["OS/2"].usWeightClass
            width = font["OS/2"].usWidthClass
            italic = font["OS/2"].fsSelection & 1 << 0
            # get the font style strings
            notascii = not p_family.isascii()
            weight_str = FONT_WEIGHT.get(weight, ("", ""))[notascii]
            width_str = FONT_WIDTH.get(width, ("", ""))[notascii]
            italic_str = FONT_STYLE.get(italic, ("", ""))[notascii]
            # create the font family string if it is empty
            if not font_setting.get((17, platformID, platEncID, langID)).strip():
                s_family = f"{weight_str} {width_str} {italic_str}".strip().replace("  ", " ")
                font_setting[(17, platformID, platEncID, langID)] = s_family
    # convert the set to a list and return it
    return list(langIDs)


def fetch_metadata(font: TTFont, font_setting: dict, langIDs):
    """Fetch the metadata from the font settings and write them back to the font file."""
    # get the font style settings
    width = font["OS/2"].usWidthClass
    weight = font["OS/2"].usWeightClass
    italic = font["OS/2"].fsSelection & 1 << 0
    # loop through all langIDs
    for platformID, platEncID, langID in langIDs:
        # get the preferred font family and subfamily
        p_family = font_setting.get((16, platformID, platEncID, langID), "")
        s_family = font_setting.get((17, platformID, platEncID, langID), "")
        # get the font style strings
        notascii = not p_family.isascii()
        weight_str = FONT_WEIGHT.get(weight, ("", ""))[notascii]
        width_str = FONT_WIDTH.get(width, ("", ""))[notascii]

        # 1 Font Family
        font_family = [p_family]
        if weight not in (400, 700):
            font_family.append(weight_str)
        if width_str:
            font_family.append(width_str)
        font_family = " ".join(font_family)
        font["name"].setName(font_family, 1, platformID, platEncID, langID)
        # 2 Font Subfamily
        font_subfamily = ["Bold"] if weight == 700 else []
        if italic:
            font_subfamily.append("Italic")
        font_subfamily = " ".join(font_subfamily)
        if not font_subfamily:
            font_subfamily = "Regular"
        font["name"].setName(font_subfamily, 2, platformID, platEncID, langID)
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
            # set the PostScript Name when the subfamily are ASCII
            if s_fam.isascii():
                ps_name = f"{p_fam}-{s_fam}".replace(" ", "-")
                font["name"].setName(ps_name, 6, platformID, platEncID, langID)
                break


def save_metadata(font_setting: dict):
    """Save the metadata of the font setting and write them back to the font file."""
    # load the font
    font = TTFont(font_setting["fontPath"])
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
        if nameID not in (1, 2, 3, 4, 6) and value and p_family and s_family:
            font["name"].setName(value, nameID, platformID, platEncID, langID)
    # save the font
    font.save(font_setting["fontPath"])


def rename_font(font_setting: dict):
    """Rename the font file based on the metadata."""
    # load the font
    font = TTFont(font_setting["fontPath"])
    # init the new name
    new_name = ""
    # loop through all records in the font
    for record in font["name"].names:
        # get the full name and version when preferred font subfamily are ASCII
        if record.nameID == 4:
            version = font_setting.get((5, record.platformID, record.platEncID, record.langID), "")
            new_name = " ".join([record.toUnicode(), version])
            s_family = font_setting.get((17, record.platformID, record.platEncID, record.langID), "")
            if not s_family.isascii():
                break
    # rename the font file
    if new_name and not os.path.exists(new_name):
        origin_path = font_setting["fontPath"]
        origin_root = os.path.dirname(origin_path)
        origin_ext = os.path.splitext(origin_path)[1]
        new_path = os.path.join(origin_root, new_name + origin_ext)
        try:
            os.rename(origin_path, new_path)
        except FileExistsError:
            print(f"File {new_path} already exists.")


def save(metadata_dfs: list[pd.DataFrame]):
    """Save the metadata of the fonts and write them back to the font files."""
    # loop through all DataFrames
    for metadata_df in metadata_dfs:
        # fill the missing values
        metadata_df.fillna("", inplace=True)
        # convert fixed values to integers
        metadata_df["fsSelection"] = metadata_df["fsSelection"].apply(lambda x: int(x, 2))
        metadata_df["usWidthClass"] = metadata_df["usWidthClass"].astype(int)
        metadata_df["usWeightClass"] = metadata_df["usWeightClass"].astype(int)
        metadata_df["numGlyphs"] = metadata_df["numGlyphs"].astype(int)
        # convert the columns to tuples
        new_columns = {col: ast.literal_eval(col) if col.startswith("(") else col for col in metadata_df.columns}
        metadata_df.rename(columns=new_columns, inplace=True)
        # loop through all font settings
        for _, font_setting in metadata_df.iterrows():
            # save the metadata
            save_metadata(font_setting)
            # rename the font file
            rename_font(font_setting)
