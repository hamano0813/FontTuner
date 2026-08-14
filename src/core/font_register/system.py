"""全局已装字体各 face 枚举：供字幕适配把系统字体并入替换选项。"""

from __future__ import annotations

import os
import struct

from core import font_io
from core.font_register.installed import _system_font_paths
from core.font_register.names import _read_name_table

_system_font_list: list[tuple[str, str, str]] | None = None


def system_font_list() -> list[tuple[str, str, str]]:
    """全局已装字体各 face 的 (family, win_name, en_name)，进程内惰性缓存一次。

    供字幕适配把系统字体并入替换选项：win_name（本地化/中文名）作显示文本，
    en_name（英文名）作匹配关键词——字幕写「微软雅黑」或「Microsoft YaHei」都能命中。
    枚举 Windows\\Fonts 目录 + HKLM 注册表登记的文件，逐个直读 name 表（TTC/OTC 取全部
    face），不写共享字体缓存。.fon 位图字体等读不了 name 表，由 is_supported 排除。
    """
    global _system_font_list
    if _system_font_list is None:
        out: list[tuple[str, str, str]] = []
        for path in _system_font_paths():
            if not font_io.is_supported(path):
                continue
            if font_io.is_collection(path):
                try:
                    with open(path, "rb") as f:
                        if f.read(4) != b"ttcf":
                            continue
                        f.read(4)  # version
                        num_faces = struct.unpack(">I", f.read(4))[0]
                except (OSError, struct.error):
                    continue
                for i in range(num_faces):
                    _append_system_font(_read_name_table(path, i), out)
            else:
                _append_system_font(_read_name_table(path), out)
        _system_font_list = out
    return _system_font_list


def _append_system_font(tup: tuple, out: list) -> None:
    """把 _read_name_table 结果按 (family, win_name, en_name) strip 后追加；全空则忽略。"""
    fam, _sub, _sub_name, win, en, _ver, _glyphs = tup
    fam, win, en = (fam or "").strip(), (win or "").strip(), (en or "").strip()
    if fam or win or en:
        out.append((fam, win, en))
