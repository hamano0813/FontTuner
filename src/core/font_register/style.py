"""字体真实字重与斜体读取（fontTools 直读 OS/2 + head）。"""

from __future__ import annotations


def font_style(path: str, font_number: int = 0) -> tuple[int, bool]:
    """字体的真实字重（OS/2 usWeightClass）与斜体标志。

    直接读字体二进制，不依赖子家族名的厂商写法差异（Hairline/Semi Bold/Demi…），
    供预览按真实字重建 QFont，保证同家族多字重文件能稳定切换渲染 face。
    font_number：TTC/OTC 内的 face 序号（默认第 1 个 face）。
    读取失败回落 (400, False)。
    """
    try:
        from fontTools.ttLib import TTFont
        font = TTFont(path, fontNumber=font_number, lazy=True)
        try:
            os2 = font.get("OS/2")
            head = font.get("head")
            weight = os2.usWeightClass if os2 is not None else 400
            italic = bool(head is not None and (head.macStyle & 0x02))
            if os2 is not None:
                italic = italic or bool(os2.fsSelection & 0x0001)
            return weight, italic
        finally:
            font.close()
    except Exception:
        return 400, False
