import pandas as pd

from fontTools.ttLib import TTFont

USED_NAME_IDS = {
    0: "版权信息 Copyright",
    1: "字体家族 Font Family",
    2: "字体子系列 Font Subfamily",
    3: "唯一标识符 Unique ID",
    4: "全名 Full Name",
    5: "版本 Version",
    6: "PS名称 PostScript Name",
    7: "商标信息 Trademark",
    8: "制造商 Manufacturer",
    9: "设计者 Designer",
    10: "描述 Description",
    11: "供应商URL Vendor URL",
    12: "设计者URL Designer URL",
    13: "许可证信息 License Description",
    14: "许可证信息URL License Info URL",
    15: "预留 Reserved",
    16: "首选字体家族 Preffered Family",
    17: "首选字体子系列 Preffered Subfamily",
    18: "兼容全名 Compatible Full",
    19: "示例文本 Sample text",
}



def get_name(font_path: str) -> list:
    font = TTFont(font_path)
    names = font['name'].names
    names = [
        {
            'font': font_path,
            'nameID': record.nameID,
            'platformID': record.platformID,
            'platEncID': record.platEncID,
            'langID': record.langID,
            'string': record.toUnicode(),
        }
        for record in names
        if record.nameID in USED_NAME_IDS
    ]
    return names


def get_os2(font_path):
    font = TTFont(font_path)
    os2 = {
        'font': font_path,
        'fsSelection': font['OS/2'].fsSelection,
        'usWeightClass': font['OS/2'].usWeightClass,
    }
    return os2


def load_metadata(font_paths: list[str]):
    name = []
    os2 = []
    for font_path in font_paths:
        if not font_path.lower().endswith('.ttf'):
            continue
        name.extend(get_name(font_path))
        os2.append(get_os2(font_path))
    name_df = pd.DataFrame(name)
    os2_df = pd.DataFrame(os2)
    return name_df, os2_df
    