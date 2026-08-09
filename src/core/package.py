"""解包/打包：TTC/OTC 集合 ⇄ 独立 TTF/OTF 文件。

解包：集合文件逐个子字体保存为独立文件，扩展名按内容判定（含 CFF 表 → .otf，否则 .ttf），
      输出名用字体内名称（家族名-字重），重名追加 _2/_3。
打包：多个单字体文件合并为一个集合文件，格式可选 自动/ttc/otc。
注意：保存后必须 close() 字体，否则 Windows 会锁住源文件。
"""

from __future__ import annotations

import os
import re
from typing import Callable, Iterable

from fontTools.ttLib import TTCollection, TTFont

COLLECTION_EXTENSIONS = (".ttc", ".otc")
FONT_EXTENSIONS = (".ttf", ".otf")

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

ProgressFn = Callable[[int, int], None]


def is_collection(path: str) -> bool:
    return path.lower().endswith(COLLECTION_EXTENSIONS)


def is_font(path: str) -> bool:
    return path.lower().endswith(FONT_EXTENSIONS)


def font_kind(font) -> str:
    """按内容判定字体类型：含 CFF 表 → otf（OpenType/CFF 轮廓），否则 ttf。"""
    return "otf" if "CFF " in font else "ttf"


def _name_record(font, *name_ids: int) -> str:
    """按 nameID 优先级取首个非空名称文本（getDebugName 取可读英文名）。"""
    name = font["name"]
    for nid in name_ids:
        value = name.getDebugName(nid)
        if value:
            return value
    return ""


def unpack_filename(font, index: int) -> str:
    """字体内名称：家族名(16→1) + '-' + 子家族名(2→17)，清洗非法字符。全空回退 font{index}。"""
    family = _name_record(font, 16, 1)
    sub = _name_record(font, 2, 17)
    text = f"{family}-{sub}" if family and sub else (family or sub)
    text = _ILLEGAL.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text or f"font{index}"


def _unique_name(base: str, used: set[str]) -> str:
    """已占用则追加 _2/_3 序号，返回可用名并登记。"""
    if base not in used:
        return base
    n = 2
    while f"{base}_{n}" in used:
        n += 1
    return f"{base}_{n}"


def list_collection_fonts(path: str) -> list[str] | None:
    """列出集合文件的子字体内部名称；读取失败返回 None。"""
    try:
        coll = TTCollection(path, lazy=True)
    except Exception:
        return None
    try:
        return [unpack_filename(font, i) for i, font in enumerate(coll.fonts)]
    finally:
        try:
            coll.close()
        except Exception:
            pass


def unpack_fonts(jobs: Iterable[tuple[str, list[int]]], out_dir: str,
                 progress: ProgressFn | None = None) -> tuple[list[str], list[tuple[str, str]]]:
    """按任务列表把集合文件的子字体解包为独立字体文件。

    jobs — [(集合路径, [子字体序号])]；序号为空列表则解出该集合全部子字体。
    Returns
    -------
    (outputs, errors) — outputs 为成功输出路径列表；errors 为 (来源, 错误信息) 列表。
    """
    outputs: list[str] = []
    errors: list[tuple[str, str]] = []
    used: set[str] = set()
    os.makedirs(out_dir, exist_ok=True)
    jobs = list(jobs)
    total = len(jobs)
    for i, (path, indices) in enumerate(jobs):
        try:
            coll = TTCollection(path, lazy=True)
        except Exception as exc:
            errors.append((path, str(exc)))
            if progress:
                progress(i + 1, total)
            continue
        try:
            # lazy 子字体共享同一 reader，必须全部处理完再统一 close，
            # 逐个 close 会关闭共享句柄导致后续子字体读取失败
            selected = indices or list(range(len(coll.fonts)))
            for index in selected:
                font = coll.fonts[index]
                try:
                    base = _unique_name(unpack_filename(font, index), used)
                    used.add(base)
                    out = os.path.join(out_dir, f"{base}.{font_kind(font)}")
                    font.save(out)
                    outputs.append(out)
                except Exception as exc:
                    errors.append((f"{os.path.basename(path)}[{index}]", str(exc)))
        finally:
            try:
                coll.close()
            except Exception:
                pass
        if progress:
            progress(i + 1, total)
    return outputs, errors


def _collection_sort_key(font) -> tuple:
    """集合内排序键：Regular（字重 400 且非斜体）排第一，其余按 字重→字宽→斜体 升序。

    Windows 双击 TTC 预览默认显示集合第一个 face，Regular 置顶预览才正常。
    """
    try:
        os2 = font["OS/2"]
        weight = int(os2.usWeightClass)
        width = int(os2.usWidthClass)
        italic = bool(os2.fsSelection & 1)
    except Exception:
        weight, width, italic = 400, 5, False
    regular = weight == 400 and not italic
    return (not regular, weight, width, italic)


def pack_fonts(srcs: Iterable[str], out_dir: str, out_name: str, fmt: str = "auto",
               progress: ProgressFn | None = None) -> tuple[str | None, list[tuple[str, str]]]:
    """把多个单字体文件打包为一个集合文件。

    集合内子字体按 _collection_sort_key 排序（Regular 优先，其余按字重→字宽→斜体）。
    fmt：auto（含 CFF → .otc，否则 .ttc）/ "ttc" / "otc"。
    Returns
    -------
    (out_path | None, errors) — 成功返回输出路径；errors 为 (来源, 错误信息) 列表。
    """
    errors: list[tuple[str, str]] = []
    fonts: list[TTFont] = []
    srcs = list(srcs)
    total = len(srcs)
    for i, path in enumerate(srcs):
        try:
            fonts.append(TTFont(path))
        except Exception as exc:
            errors.append((os.path.basename(path), str(exc)))
        if progress:
            progress(i + 1, total)
    if not fonts:
        return None, errors

    fonts.sort(key=_collection_sort_key)  # Regular 置顶，Windows 预览取第一个 face

    out_name = _ILLEGAL.sub("", (out_name or "").strip())
    if not out_name:
        out_name = "collection"
    if fmt == "auto":
        ext = ".otc" if any("CFF " in f for f in fonts) else ".ttc"
    else:
        ext = "." + fmt

    out = os.path.join(out_dir, out_name + ext)
    try:
        os.makedirs(out_dir, exist_ok=True)
        coll = TTCollection()
        coll.fonts = fonts
        coll.save(out)
    except Exception as exc:
        errors.append((os.path.basename(out), str(exc)))
        out = None
    finally:
        for f in fonts:
            try:
                f.close()
            except Exception:
                pass
    return out, errors
