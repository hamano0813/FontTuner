"""会话级注册/注销：AddFontResourceEx + WM_FONTCHANGE。

会话级注册：勾选即把字体加入 Windows 系统字体表，所有程序可枚举（当前会话）；
取消勾选即注销，重启自然失效。
"""

from __future__ import annotations

import ctypes
import os

_HWND_BROADCAST = 0xFFFF
_WM_FONTCHANGE = 0x001D
# 不带标志 = 加入系统字体表（全会话应用可见）；FR_PRIVATE 才是仅当前进程
_RESOURCE_FLAGS = 0

_gdi32 = ctypes.WinDLL("gdi32")
_user32 = ctypes.WinDLL("user32")
_gdi32.AddFontResourceExW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
_gdi32.AddFontResourceExW.restype = ctypes.c_int
_gdi32.RemoveFontResourceExW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
_gdi32.RemoveFontResourceExW.restype = ctypes.c_int


def register_font(path: str) -> bool:
    """把字体文件注册到 Windows 系统字体表（会话级）。成功返回 True。"""
    if not os.path.isfile(path):
        return False
    if _gdi32.AddFontResourceExW(path, _RESOURCE_FLAGS, None) > 0:
        _notify_font_change()
        return True
    return False


def unregister_font(path: str) -> bool:
    """从系统字体表注销字体。成功返回 True（被占用时会失败）。

    GDI 对同一字体文件按路径计数：上次运行勾选、注册回滚、重复勾选都会使引用数
    累加，单次 RemoveFontResourceEx 只减一个引用，字体仍会残留在系统字体表。
    因此循环 Remove 直到失败，把该路径的引用全部排空（被占用时首次即失败，循环即停）。
    """
    removed = False
    while _gdi32.RemoveFontResourceExW(path, _RESOURCE_FLAGS, None):
        removed = True
    if removed:
        _notify_font_change()
        return True
    return False


def _notify_font_change() -> None:
    """广播 WM_FONTCHANGE，让已运行的应用刷新字体列表。"""
    _user32.PostMessageW(_HWND_BROADCAST, _WM_FONTCHANGE, 0, 0)
