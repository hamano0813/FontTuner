"""字体加载/保存编排：load_entries / save_entries。"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, Iterable

from fontTools.ttLib import TTCollection

from core import font_io, mapping, metadata as _metadata
from core.models import FontEntry

ProgressFn = Callable[[int, int], None]


def load_entries(paths: Iterable[str], progress: ProgressFn | None = None) -> tuple[list[FontEntry], list[tuple[str, str]]]:
    """展开路径、读取每个子字体的逻辑字段。

    Returns
    -------
    (entries, errors) — errors 为 (路径, 错误信息) 列表，单文件失败不中断整批。
    """
    files = font_io.collect_font_files(paths)
    entries: list[FontEntry] = []
    errors: list[tuple[str, str]] = []
    total = len(files)
    for i, path in enumerate(files):
        try:
            for index, font in font_io.open_fonts(path):
                entries.append(mapping.read_entry(path, index, font))
        except Exception as exc:
            errors.append((path, str(exc)))
        if progress:
            progress(i + 1, total)
    return entries, errors


def save_entries(entries: Iterable[FontEntry], progress: ProgressFn | None = None) -> list[tuple[str, str]]:
    """保存所有字体，按文件分组，集合文件一次写回。

    Returns
    -------
    errors — (路径, 错误信息) 列表，单字体失败不中断整批。
    """
    grouped: dict[str, list[FontEntry]] = defaultdict(list)
    for entry in entries:
        grouped[entry.font_path].append(entry)

    errors: list[tuple[str, str]] = []
    total = len(grouped)
    for i, (path, group) in enumerate(grouped.items()):
        try:
            if font_io.is_collection(path):
                _save_collection(path, group)
            else:
                _save_single(path, group)
        except PermissionError:
            errors.append((path, "权限不足，无法写入"))
        except Exception as exc:
            errors.append((path, str(exc)))
        if progress:
            progress(i + 1, total)
    return errors


def _save_single(path: str, group: list[FontEntry]) -> None:
    entry = group[0]
    ok = _metadata.save_metadata(
        mapping.build_font_setting(entry),
        remove_groups=mapping.compute_remove_groups(entry),
    )
    if not ok:
        raise PermissionError(f"保存失败：{path}")


def _save_collection(path: str, group: list[FontEntry]) -> None:
    collection = TTCollection(path)
    for entry in group:
        font = collection.fonts[entry.font_index]
        _metadata.apply_font_settings(
            font,
            mapping.build_font_setting(entry),
            remove_groups=mapping.compute_remove_groups(entry),
        )
    # 全部子字体应用成功才写回一次，失败不落盘
    collection.save(path)
