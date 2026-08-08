"""字体文件打开/遍历：单字体与集合文件（TTC/OTC）分流。"""

from __future__ import annotations

import os
from typing import Iterable

from fontTools.ttLib import TTCollection, TTFont

FONT_EXTENSIONS = (".ttf", ".otf", ".ttc", ".otc")
COLLECTION_EXTENSIONS = (".ttc", ".otc")


def is_supported(path: str) -> bool:
    return path.lower().endswith(FONT_EXTENSIONS)


def is_collection(path: str) -> bool:
    return path.lower().endswith(COLLECTION_EXTENSIONS)


def collect_font_files(paths: Iterable[str]) -> list[str]:
    """把文件/文件夹路径展开为字体文件列表（递归、去重、保序）。"""
    files: list[str] = []
    seen: set[str] = set()
    for path in paths:
        path = str(path)
        if os.path.isdir(path):
            for root, _, names in os.walk(path):
                for name in names:
                    full = os.path.join(root, name)
                    if is_supported(full) and full not in seen:
                        seen.add(full)
                        files.append(full)
        elif is_supported(path) and path not in seen:
            seen.add(path)
            files.append(path)
    return files


def open_fonts(path: str) -> list[tuple[int, TTFont]]:
    """按扩展名打开字体文件，返回 [(index, TTFont)]。

    单字体（.ttf/.otf）返回 [(0, font)]；集合（.ttc/.otc）逐个子字体返回。
    """
    if is_collection(path):
        collection = TTCollection(path, lazy=True)
        return [(i, font) for i, font in enumerate(collection.fonts)]
    return [(0, TTFont(path, lazy=True))]
