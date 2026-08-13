# 编辑器字宽列写死的简体枚举（1-9），也是解析 {width_sc} 等占位符时无模板时的默认来源
WIDTH_LABELS = {
    1: "极窄", 2: "特窄", 3: "窄", 4: "半窄", 5: "正常",
    6: "半宽", 7: "宽", 8: "特宽", 9: "极宽",
}

# 字宽档位的 OpenType 标准英文名（usWidthClass 1-9），模板对话框设计值列显示用
WIDTH_NAMES_EN = {
    1: "UltraCondensed", 2: "ExtraCondensed", 3: "Condensed", 4: "SemiCondensed",
    5: "Normal", 6: "SemiExpanded", 7: "Expanded", 8: "ExtraExpanded", 9: "UltraExpanded",
}

# 新建模板时字重表预填的 100-900 九档默认（usWeightClass 的 Apple 命名 + 四语言硬编码翻译）
WEIGHT_TRANSLATIONS = {
    100: {"SC": "极细", "TC": "極細", "JA": "極細", "EN": "Thin"},
    200: {"SC": "特细", "TC": "特細", "JA": "特細", "EN": "ExtraLight"},
    300: {"SC": "细",   "TC": "細",   "JA": "細",   "EN": "Light"},
    400: {"SC": "常规", "TC": "標準", "JA": "標準", "EN": "Regular"},
    500: {"SC": "中等", "TC": "中等", "JA": "中",   "EN": "Medium"},
    600: {"SC": "半粗", "TC": "半粗", "JA": "半太", "EN": "SemiBold"},
    700: {"SC": "粗",   "TC": "粗",   "JA": "太字", "EN": "Bold"},
    800: {"SC": "特粗", "TC": "特粗", "JA": "特太", "EN": "ExtraBold"},
    900: {"SC": "极粗", "TC": "極粗", "JA": "極太", "EN": "Black"},
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
