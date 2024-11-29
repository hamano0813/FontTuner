FONT_WEIGHT = {
    100: ("UltraLight", "极细", "極細"),
    150: ("ExtraLight", "特细", "特細"),
    200: ("Thin", "纤细", "纖細"),
    300: ("Light", "细体", "細體"),
    325: ("SemiLight", "准细", "準細"),
    350: ("DemiLight", "半细", "半細"),
    375: ("Book", "标准", "標準"),
    400: ("Regular", "常规", "常規"),
    500: ("Medium", "中等", "中等"),
    600: ("DemiBold", "半粗", "半粗"),
    650: ("SemiBold", "准粗", "準粗"),
    700: ("Bold", "粗体", "粗體"),
    800: ("ExtraBold", "特粗", "特粗"),
    850: ("Heavy", "重粗", "重粗"),
    900: ("Black", "粗黑", "粗黑"),
    950: ("UltraBlack", "极黑", "極黑"),
}

FONT_WIDTH = {
    1: ("UltraCondensed", "极窄", "極窄"),
    2: ("ExtraCondensed", "特窄", "特窄"),
    3: ("Condensed", "窄", "窄"),
    4: ("SemiCondensed", "半窄", "半窄"),
    5: ("", "", ""),
    6: ("SemiExtended", "半宽", "半宽"),
    7: ("Extended", "宽", "宽"),
    8: ("ExtraExtended", "特宽", "特宽"),
    9: ("UltraExtended", "极宽", "极宽"),
}

FONT_STYLE = {
    0b1 << 0: ("Italic", "斜体", "斜體"),
    0b1 << 1: ("Underline", "下划线", "下劃線"),
    0b1 << 2: ("Negative", "反色", "反色"),
    0b1 << 3: ("Outline", "轮廓", "輪廓"),
    0b1 << 4: ("Strikeout", "删除线", "刪除線"),
    0b1 << 4: ("Shadow", "阴影", "陰影"),
    0b1 << 5: ("Bold", "粗体", "粗體"),
    0b1 << 6: ("Regular", "正常", "正常"),
}

MAC_STYLE = {
    0b1 << 0: ("Bold", "粗体", "粗體"),
    0b1 << 1: ("Italic", "斜体", "斜體"),
    0b1 << 2: ("Underline", "下划线", "下劃線"),
    0b1 << 3: ("Outline", "轮廓", "輪廓"),
    0b1 << 4: ("Shadow", "阴影", "陰影"),
    0b1 << 5: ("Condensed", "窄体", "窄體"),
    0b1 << 6: ("Extended", "宽体", "寬體"),
}
