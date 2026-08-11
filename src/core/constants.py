# 四元组：(English, 简体, 繁體, 日文)。日文为默认标签（缩写码方案），可在设置页「字重/字宽翻译」中编辑。
FONT_WEIGHT = {
    100: ("UltraLight", "极细", "極細", "UL"),
    150: ("ExtraLight", "特细", "特細", "EL"),
    200: ("Thin", "纤细", "纖細", "T"),
    300: ("Light", "细体", "細體", "L"),
    325: ("SemiLight", "准细", "準細", "SL"),
    350: ("DemiLight", "半细", "半細", "DL"),
    375: ("Book", "标准", "標準", "BK"),
    400: ("Regular", "常规", "常規", "R"),
    500: ("Medium", "中等", "中等", "M"),
    600: ("DemiBold", "半粗", "半粗", "DB"),
    650: ("SemiBold", "准粗", "準粗", "SB"),
    700: ("Bold", "粗体", "粗體", "B"),
    800: ("ExtraBold", "特粗", "特粗", "EB"),
    850: ("Heavy", "重粗", "重粗", "H"),
    900: ("Black", "粗黑", "粗黑", "BL"),
    950: ("UltraBlack", "极黑", "極黑", "UB"),
}

FONT_WIDTH = {
    1: ("UltraCondensed", "极窄", "極窄", "UC"),
    2: ("ExtraCondensed", "特窄", "特窄", "EC"),
    3: ("Condensed", "窄", "窄", "C"),
    4: ("SemiCondensed", "半窄", "半窄", "SC"),
    5: ("Normal", "正常", "正常", "Normal"),
    6: ("SemiExtended", "半宽", "半宽", "SE"),
    7: ("Extended", "宽", "宽", "E"),
    8: ("ExtraExtended", "特宽", "特宽", "EE"),
    9: ("UltraExtended", "极宽", "极宽", "UE"),
}

FONT_STYLE = {
    0b1 << 0: ("Italic", "斜体", "斜體"),
    0b1 << 1: ("Underline", "下划线", "下劃線"),
    0b1 << 2: ("Negative", "反色", "反色"),
    0b1 << 3: ("Outline", "轮廓", "輪廓"),
    0b1 << 4: ("Strikeout", "删除线", "刪除線"),
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
