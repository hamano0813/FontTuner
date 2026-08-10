"""字体文件打开/遍历：单字体与集合文件（TTC/OTC）分流。"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterable, Iterator

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


@contextmanager
def open_fonts(path: str) -> Iterator[list[tuple[int, TTFont]]]:
    """按扩展名打开字体文件，yield [(index, TTFont)]；退出时统一关闭。

    单字体（.ttf/.otf）yield [(0, font)]；集合（.ttc/.otc）逐个子字体返回。
    读取后必须关闭，否则 lazy TTFont 的句柄会锁住文件（Windows 上无法删除/写入）。
    集合子字体共享同一 reader，须全部读取后再统一 close 整个集合；
    逐个 close 会关闭共享句柄导致后续子字体读取失败。
    """
    if is_collection(path):
        collection = TTCollection(path, lazy=True)
        try:
            yield [(i, font) for i, font in enumerate(collection.fonts)]
        finally:
            try:
                collection.close()
            except Exception:
                pass
    else:
        font = TTFont(path, lazy=True)
        try:
            yield [(0, font)]
        finally:
            try:
                font.close()
            except Exception:
                pass
