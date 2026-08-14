"""系统已装字体检测：注册表 Fonts 键（HKLM + HKCU）+ Windows\\Fonts 目录。

系统已装字体（注册表 Fonts 键 / Windows\\Fonts 目录）在树里仅标记，不提供勾选，
避免误卸系统字体。
"""

from __future__ import annotations

import os
import winreg


def _windows_fonts_dir() -> str:
    return os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")


def _registry_font_paths_for(hive) -> set[str]:
    """单个注册表 hive 的 Fonts 键登记的字体，统一为 normcase 全路径。

    系统字体登记的是相对文件名（实际在 Windows\\Fonts 下）→ 拼出全路径；
    用户安装字体登记的是绝对路径 → 直接用。
    """
    paths: set[str] = set()
    win_fonts = _windows_fonts_dir()
    try:
        key = winreg.OpenKey(hive, r"Software\Microsoft\Windows NT\CurrentVersion\Fonts")
    except OSError:
        return paths
    try:
        for i in range(winreg.QueryInfoKey(key)[1]):
            _, data, _ = winreg.EnumValue(key, i)
            if not isinstance(data, str) or not data.strip():
                continue
            if os.path.isabs(data):
                paths.add(os.path.normcase(data))
            else:
                paths.add(os.path.normcase(os.path.join(win_fonts, data)))
    finally:
        key.Close()
    return paths


def _registry_font_paths() -> set[str]:
    """注册表 Fonts 键登记的字体（HKLM + HKCU）。"""
    return (_registry_font_paths_for(winreg.HKEY_LOCAL_MACHINE)
            | _registry_font_paths_for(winreg.HKEY_CURRENT_USER))


def _windows_fonts_dir_files() -> set[str]:
    """C:\\Windows\\Fonts 目录下的字体文件全路径（normcase）。"""
    win_fonts = _windows_fonts_dir()
    try:
        return {os.path.normcase(os.path.join(win_fonts, name)) for name in os.listdir(win_fonts)}
    except OSError:
        return set()


def _system_font_paths() -> set[str]:
    """全局已装字体文件路径：Windows\\Fonts 目录 + HKLM 注册表登记（不含 HKCU 用户字体）。"""
    return _windows_fonts_dir_files() | _registry_font_paths_for(winreg.HKEY_LOCAL_MACHINE)


_installed_cache: set[str] | None = None


def installed_font_set() -> set[str]:
    """已安装字体文件集合（缓存）：注册表登记 + Windows\\Fonts 目录，按全路径判定。"""
    global _installed_cache
    if _installed_cache is None:
        _installed_cache = _registry_font_paths() | _windows_fonts_dir_files()
    return _installed_cache


def is_font_installed(path: str) -> bool:
    """该字体文件是否已由系统安装（全路径匹配，同名副本不会误判）。"""
    return os.path.normcase(os.path.abspath(path)) in installed_font_set()
