"""mtime/size 增量扫描缓存（data/fontmgr_cache.json）。

重扫时按 size+mtime 命中缓存直接复用名称读取结果，避免重复打开字体文件；
硬重扫（重新扫描按钮）跳过缓存，对已存在文件也强制重读并回写刷新。
"""

from __future__ import annotations

import json
import os
import struct

from core.font_register.names import _read_name_table
from core.paths import DATA_DIR

_CACHE_PATH = DATA_DIR / "fontmgr_cache.json"
# 缓存结构版本：win_name 语义（家族名优先、语言优先级 简英日繁）变更时 +1，使旧缓存自动失效重读
_CACHE_VERSION = 7
_cache: dict = {}
# 硬重扫标志：重新扫描按钮置位，使名称读取跳过 mtime/size 缓存，
# 对已存在的文件也强制重读名称表，并回写刷新缓存条目
_hard_rescan = False


def set_hard_rescan(flag: bool) -> None:
    global _hard_rescan
    _hard_rescan = bool(flag)


def load_cache() -> None:
    """载入扫描缓存（data/fontmgr_cache.json）。"""
    global _cache
    try:
        if _CACHE_PATH.exists():
            _cache = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        else:
            _cache = {}
    except (OSError, ValueError):
        _cache = {}


def save_cache() -> None:
    """把内存缓存写回磁盘，供下次扫描增量复用。"""
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(_cache, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _cached_names(path: str) -> tuple[str, str, str, str, str, str, int]:
    """按 size+mtime 命中缓存则直接复用名称（不打开文件）；否则 struct 直读并更新缓存。

    返回 (family, subfamily, sub_name, win_name, en_name, version, glyphs)，与 _read_name_table 顺序一致。
    旧缓存条目缺 win_name/en_name/version/glyphs 时回退 family / 空值。
    """
    key = os.path.normcase(os.path.abspath(path))
    try:
        st = os.stat(path)
        size, mtime = st.st_size, st.st_mtime
    except OSError:
        return "", "", "", "", "", "", 0
    cached = _cache.get(key)
    if (not _hard_rescan and cached and cached.get("v") == _CACHE_VERSION
            and cached.get("size") == size and cached.get("mtime") == mtime):
        family = cached.get("family") or ""
        subfamily = cached.get("subfamily") or ""
        sub_name = cached.get("sub_name") or subfamily
        win_name = cached.get("win_name")
        en_name = cached.get("en_name")
        version = cached.get("version") or ""
        glyphs = cached.get("glyphs") or 0
        return family, subfamily, sub_name, (
            win_name if win_name is not None else family), (
            en_name if en_name is not None else family), version, glyphs
    family, subfamily, sub_name, win_name, en_name, version, glyphs = _read_name_table(path)
    _cache[key] = {"v": _CACHE_VERSION, "family": family, "subfamily": subfamily,
                   "sub_name": sub_name,
                   "win_name": win_name, "en_name": en_name,
                   "version": version, "glyphs": glyphs,
                   "size": size, "mtime": mtime}
    return family, subfamily, sub_name, win_name, en_name, version, glyphs


def _cached_faces(path: str) -> list[dict]:
    """读取 TTC/OTC 全部 face 的名称列表（按 size+mtime+版本 缓存）。

    每个 face：{family, subfamily, win_name, en_name, version, glyphs}；读取失败返回 []。
    """
    key = os.path.normcase(os.path.abspath(path))
    try:
        st = os.stat(path)
        size, mtime = st.st_size, st.st_mtime
    except OSError:
        return []
    cached = _cache.get(key)
    if (not _hard_rescan and cached and cached.get("v") == _CACHE_VERSION
            and cached.get("size") == size and cached.get("mtime") == mtime
            and isinstance(cached.get("faces"), list)):
        return cached["faces"]
    num = 0
    try:
        with open(path, "rb") as f:
            if f.read(4) != b"ttcf":
                return []
            f.read(4)  # version
            num = struct.unpack(">I", f.read(4))[0]
    except (OSError, struct.error):
        return []
    faces = []
    for i in range(num):
        family, subfamily, sub_name, win_name, en_name, version, glyphs = _read_name_table(path, i)
        faces.append({"family": family, "subfamily": subfamily, "sub_name": sub_name,
                      "win_name": win_name, "en_name": en_name,
                      "version": version, "glyphs": glyphs})
    entry = _cache.get(key) or {}
    entry["v"] = _CACHE_VERSION
    entry["size"] = size
    entry["mtime"] = mtime
    entry["faces"] = faces
    _cache[key] = entry
    return faces
