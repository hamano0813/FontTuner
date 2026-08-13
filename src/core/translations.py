"""语言常量与 Windows 语言 ID → 逻辑语言 映射。

字重/字宽/斜体的文本不再由全局翻译方案提供，改由「信息模板」的映射表按
模板列查表产生（见 core/templates.py 的 template_label）。此模块仅保留与
语言相关的公共常量与映射。
"""

LANGS = ("SC", "TC", "JA", "EN")
_LANG_INDEX = {"EN": 0, "SC": 1, "TC": 2, "JA": 3}


def lang_of(lang_id: int) -> str:
    """Windows 语言 ID → 逻辑语言（未识别回落英文）。"""
    if lang_id == 0x0804:
        return "SC"
    if lang_id == 0x0404:
        return "TC"
    if lang_id == 0x0411:
        return "JA"
    return "EN"
