FONT_WEIGHT = {
    150: ("Hairline", "特丝"),
    200: ("Thin", "特纤"),
    250: ("UltraLight", "特细"),
    275: ("ExtraLight", "超细"),
    300: ("Light", "细体"),
    350: ("SemiLight", "稍细"),
    400: ("Regular", "正常"),
    500: ("Medium", "中等"),
    550: ("DemiBold", "微粗"),
    600: ("SemiBold", "稍粗"),
    700: ("Bold", "粗体"),
    800: ("ExtraBold", "超粗"),
    850: ("UltraBold", "特粗"),
    900: ("Heavy", "特浓"),
    950: ("Black", "特黑"),
}

HY_WEIGHT = {
    50: ("Feather", "羽", "羽"),  # 25
    100: ("Hairline", "丝", "絲"),  # 30
    200: ("Thin", "纤", "纖"),  # 35
    250: ("Slim", "细", "細"),  # 40
    300: ("Light", "轻", "輕"),  # 45
    350: ("Book", "书", "書"),  # 50
    400: ("Regular", "准", "準"),  # 55
    500: ("Medium", "中", "中"),  # 60
    550: ("Semi", "次", "次"),  # 65
    600: ("Demi", "半", "半"),  # 70
    700: ("Bold", "粗", "粗"),  # 75
    750: ("Heavy", "重", "重"),  # 80
    800: ("Dense", "厚", "厚"),  # 85
    850: ("Extra", "极", "極"),  # 90
    900: ("Ultra", "超", "超"),  # 95
    950: ("Black", "黑", "黑"),  # 105
}

FONT_WIDTH = {
    1: ("UltraCondensed", "特窄"),
    2: ("ExtraCondensed", "超窄"),
    3: ("Condensed", "窄"),
    4: ("SemiCondensed", "稍窄"),
    5: ("", ""),
    6: ("SemiExtended", "稍宽"),
    7: ("Extended", "宽"),
    8: ("ExtraExtended", "超宽"),
    9: ("UltraExtended", "特宽"),
}

FONT_STYLE = {
    0b1 << 0: ("Italic", "斜体"),
    0b1 << 1: ("Underline", "下划线"),
    0b1 << 2: ("Negative", "反色"),
    0b1 << 3: ("Outlined", "轮廓"),
    0b1 << 4: ("Strikeout", "删除线"),
    0b1 << 5: ("Bold", "粗体"),
    0b1 << 6: ("Regular", "正常"),
}

MAC_STYLE = {
    0b1 << 0: ("Bold", "粗体"),
    0b1 << 1: ("Italic", "斜体"),
    0b1 << 2: ("Underline", "下划线"),
    0b1 << 3: ("Outline", "轮廓"),
    0b1 << 4: ("Shadow", "阴影"),
    0b1 << 5: ("Condensed", "窄体"),
    0b1 << 6: ("Extended", "宽体"),
}
