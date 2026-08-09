"""字体加载/保存编排：load_entries / save_entries。"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Callable, Iterable

from fontTools.ttLib import TTCollection

from core import font_io, mapping, metadata as _metadata
from core.models import LANGS, FontEntry
from core.translations import italic_label, weight_label, width_label

ProgressFn = Callable[[int, int], None]


def sort_entries(entries: list[FontEntry]) -> list[FontEntry]:
    """按 首选家族名(nameID 16，缺省回退家族名 1) → 字重 → 字宽 就地排序。

    排序只在载入/追加时调用；编辑/模板应用不触发，避免表格行随字段改动乱跳。
    """
    def key(e: FontEntry):
        names = e.names.get("EN", {})
        family = names.get(16) or names.get(1) or ""
        return (family.casefold(), e.us_weight_class, e.us_width_class)
    entries.sort(key=key)
    return entries


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


# ---------------------------------------------------------------- 重命名

DEFAULT_RENAME_TEMPLATE = "{preferred_family_sc} {weight_sc} {width_sc} {version_sc}"
_NAME_PRIORITY = ("SC", "TC", "JA", "EN")   # 旧占位符 首选家族名：简>繁>日>英
_FIELD_PRIORITY = ("EN", "SC", "TC", "JA")  # 旧占位符 字重/字宽/版本：英>简>繁>日
_LANG_CODE = {"SC": "sc", "TC": "tc", "JA": "jp", "EN": "en"}  # 语言后缀
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# 重命名模板变量（中文列名 → 占位符），xx 为语言后缀 sc/tc/jp/en
RENAME_PLACEHOLDERS = (
    ("字体名", "{name_xx}"),
    ("字重", "{weight_xx}"),
    ("字宽", "{width_xx}"),
    ("斜体", "{italic_xx}"),
    ("字符集", "{charset_xx}"),
    ("家族名", "{family_xx}"),
    ("子家族名", "{subfamily_xx}"),
    ("首选家族名", "{preferred_family_xx}"),
    ("版本号", "{version_xx}"),
    ("字重数值", "{weight_num}"),
    ("字宽数值", "{width_num}"),
)


def rename_placeholder_help() -> str:
    """生成「中文列名 - {占位符}」变量说明，并注明语言后缀。"""
    lines = "\n".join(f"{cn} - {ph}" for cn, ph in RENAME_PLACEHOLDERS)
    return lines + "\n\nxx 可替换为四种语言：sc/tc/jp/en（简/繁/日/英）"


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"  # 未识别的占位符原样保留


def _first_label(label_fn, value: int, priority: tuple = _FIELD_PRIORITY) -> str:
    """按语言优先级取第一个非空标签；全空返回空串。"""
    for lang in priority:
        text = (label_fn(value, lang) or "").strip()
        if text:
            return text
    return ""


def _first_nonempty(entry: FontEntry, name_id: int, priority: tuple) -> str:
    """按语言优先级取第一个非空 name 字段值。"""
    for lang in priority:
        v = (entry.names[lang].get(name_id) or "").strip()
        if v:
            return v
    return ""


def _rename_vars(entry: FontEntry) -> dict[str, str]:
    """重命名模板可用变量：逐语言 {字段_xx} + 数值 + 旧版占位符（兼容）。"""
    vars = {"weight_num": str(entry.us_weight_class), "width_num": str(entry.us_width_class)}
    for lang in LANGS:
        code = _LANG_CODE[lang]
        names = entry.names[lang]
        vars[f"name_{code}"] = entry.temp_names[lang]
        vars[f"weight_{code}"] = weight_label(entry.us_weight_class, lang)
        vars[f"width_{code}"] = width_label(entry.us_width_class, lang)
        vars[f"italic_{code}"] = italic_label(entry.italic(), lang)
        vars[f"charset_{code}"] = entry.charsets[lang]
        vars[f"family_{code}"] = names.get(1, "")
        vars[f"subfamily_{code}"] = names.get(2, "")
        vars[f"preferred_family_{code}"] = names.get(16, "")
        vars[f"version_{code}"] = names.get(5, "")
    # 兼容旧版占位符（按语言优先级解析）
    vars.update({
        "首选家族名": _first_nonempty(entry, 16, _NAME_PRIORITY),
        "家族名": _first_nonempty(entry, 16, _NAME_PRIORITY) or _first_nonempty(entry, 1, _NAME_PRIORITY),
        "weight": _first_label(weight_label, entry.us_weight_class),
        "width": _first_label(width_label, entry.us_width_class),
        "version": _first_nonempty(entry, 5, _FIELD_PRIORITY),
    })
    return vars


def _build_filename(entry: FontEntry, template: str) -> str | None:
    """按重命名模板 + 变量生成新文件名；解析后清理非法字符、合并多余空格。

    变量为空时其占位符替换为空串，连续空格被合并（宽度正常为空 → 不再留空格）。
    解析结果为空返回 None（该文件跳过重命名）。
    """
    vars = _rename_vars(entry)
    # 模板引用家族名但字体完全没有 → 跳过，避免命名成 "Regular.ttf" 这类无意义文件名
    uses_family = any(x in template for x in ("{首选家族名}", "{家族名}", "{preferred_family", "{family_"))
    if uses_family:
        has_family = any((entry.names[lang].get(16) or entry.names[lang].get(1) or "").strip() for lang in LANGS)
        if not has_family:
            return None
    text = template.format_map(_SafeDict(vars))
    text = _ILLEGAL.sub("", text)
    text = re.sub(r"\s+", " ", text).strip().rstrip(". ")
    if not text:
        return None
    ext = os.path.splitext(entry.font_path)[1].lower()
    if not text.lower().endswith(ext):
        text += ext
    return text


def rename_entries(entries, template: str | None = None,
                   release_font: Callable[[str], None] | None = None) -> tuple[int, int, list[tuple[str, str]]]:
    """按重命名模板重命名载入字体的文件，按文件分组（集合文件一次一个文件名）。

    release_font(path)：重命名前释放应用对该字体的注册（解除本进程占用锁）。
    返回 (renamed, skipped, errors)；errors 为 (旧路径, 错误信息)。
    """
    template = template or DEFAULT_RENAME_TEMPLATE
    grouped: dict[str, list[FontEntry]] = defaultdict(list)
    for entry in entries:
        grouped[entry.font_path].append(entry)

    renamed = skipped = 0
    errors: list[tuple[str, str]] = []
    for path, group in grouped.items():
        try:
            new_name = _build_filename(group[0], template)
            if new_name is None:
                skipped += 1  # 模板解析结果为空，无法命名
                continue
            new_path = os.path.join(os.path.dirname(path), new_name)
            if os.path.normcase(new_path) == os.path.normcase(path):
                skipped += 1  # 文件名已符合格式
                continue
            if release_font is not None:
                release_font(path)
            os.rename(path, new_path)
            for entry in group:
                entry.font_path = new_path
            renamed += 1
        except PermissionError:
            errors.append((path, "文件被占用（可能被其他程序或系统字体预览锁定）"))
        except OSError as exc:
            errors.append((path, str(exc)))
    return renamed, skipped, errors


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
