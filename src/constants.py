import pandas as pd

FONT_WEIGHT = {
    150: ("Hairline", "特丝"),
    200: ("Thin", "特纤"),
    250: ("UltraLight", "特细"),
    275: ("ExtraLight", "超细"),
    300: ("Light", "细体"),
    350: ("SemiLight", "半细"),
    400: ("Regular", "正常"),
    500: ("Medium", "中等"),
    550: ("DemiBold", "次粗"),
    600: ("SemiBold", "半粗"),
    700: ("Bold", "粗体"),
    800: ("ExtraBold", "超粗"),
    850: ("UltraBold", "特粗"),
    900: ("Heavy", "特浓"),
    950: ("Black", "特黑"),
}

FONT_WIDTH = {
    1: ("UltraCondensed", "特窄"),
    2: ("ExtraCondensed", "超窄"),
    3: ("Condensed", "偏窄"),
    4: ("SemiCondensed", "稍窄"),
    5: ("Medium", "中等"),
    6: ("SemiExpanded", "稍宽"),
    7: ("Expanded", "偏宽"),
    8: ("ExtraExpanded", "超宽"),
    9: ("UltraExpanded", "特宽"),
}


weight_df = pd.DataFrame(FONT_WEIGHT.values(), index=FONT_WEIGHT.keys(), columns=["English", "Chinese"])
width_df = pd.DataFrame(FONT_WIDTH.values(), index=FONT_WIDTH.keys(), columns=["English", "Chinese"])