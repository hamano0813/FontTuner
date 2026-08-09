"""字体系统级注册（会话级）：AddFontResourceEx + WM_FONTCHANGE，以及系统已装字体检测。

会话级注册：勾选即把字体加入 Windows 系统字体表，所有程序可枚举（当前会话）；
取消勾选即注销，重启自然失效。系统已装字体（注册表 Fonts 键 / Windows\\Fonts 目录）
在树里仅标记，不提供勾选，避免误卸系统字体。
"""

from __future__ import annotations

import ctypes
import json
import os
import struct
import winreg

from core import font_io
from core.paths import DATA_DIR

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


# ---------------------------------------------------------------- 注册/注销

def register_font(path: str) -> bool:
    """把字体文件注册到 Windows 系统字体表（会话级）。成功返回 True。"""
    if not os.path.isfile(path):
        return False
    if _gdi32.AddFontResourceExW(path, _RESOURCE_FLAGS, None) > 0:
        _notify_font_change()
        return True
    return False


def unregister_font(path: str) -> bool:
    """从系统字体表注销字体。成功返回 True（被占用时会失败）。"""
    if _gdi32.RemoveFontResourceExW(path, _RESOURCE_FLAGS, None):
        _notify_font_change()
        return True
    return False


def _notify_font_change() -> None:
    """广播 WM_FONTCHANGE，让已运行的应用刷新字体列表。"""
    _user32.PostMessageW(_HWND_BROADCAST, _WM_FONTCHANGE, 0, 0)


# ---------------------------------------------------------------- 已装检测

def _windows_fonts_dir() -> str:
    return os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")


def _registry_font_paths() -> set[str]:
    """注册表 Fonts 键登记的字体（HKLM + HKCU），统一为 normcase 全路径。

    系统字体登记的是相对文件名（实际在 Windows\\Fonts 下）→ 拼出全路径；
    用户安装字体登记的是绝对路径 → 直接用。
    """
    paths: set[str] = set()
    win_fonts = _windows_fonts_dir()
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            key = winreg.OpenKey(hive, r"Software\Microsoft\Windows NT\CurrentVersion\Fonts")
        except OSError:
            continue
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


def _windows_fonts_dir_files() -> set[str]:
    """C:\\Windows\\Fonts 目录下的字体文件全路径（normcase）。"""
    win_fonts = _windows_fonts_dir()
    try:
        return {os.path.normcase(os.path.join(win_fonts, name)) for name in os.listdir(win_fonts)}
    except OSError:
        return set()


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


# ---------------------------------------------------------------- 扫描

def _read_name_table_family(path: str) -> str | None:
    """struct 直读 name 表家族名（nameID 16/1，TTC 取第一个子字体）。

    只定位并解析 'name' 表，避免 fontTools 全量打开文件。失败返回 None。
    """
    try:
        with open(path, "rb") as f:
            magic = f.read(4)
            base = 0
            if magic == b"ttcf":
                f.read(4)  # version
                num_fonts = struct.unpack(">I", f.read(4))[0]
                if num_fonts < 1:
                    return None
                base = struct.unpack(">I", f.read(4))[0]  # 第一个子字体 sfnt 偏移
                f.seek(base)
                magic = f.read(4)
            if magic not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
                return None
            header = f.read(8)  # numTables/searchRange/entrySelector/rangeShift
            if len(header) < 8:
                return None
            num_tables = struct.unpack(">H", header[0:2])[0]
            name_off = name_len = None
            for _ in range(num_tables):
                rec = f.read(16)
                if len(rec) < 16:
                    return None
                offset, length = struct.unpack(">II", rec[8:16])
                if rec[0:4] == b"name":
                    name_off, name_len = offset, length
                    break
            if name_off is None:
                return None
            # TTC 子字体的表偏移是绝对文件偏移（实测 fontTools 与 Windows 字体均如此），
            # base 只用于定位 sfnt 头，读表数据直接用 name_off
            f.seek(name_off)
            data = f.read(name_len)
            if len(data) < 6:
                return None
            count = struct.unpack(">H", data[2:4])[0]
            string_offset = struct.unpack(">H", data[4:6])[0]
            records = []
            for i in range(count):
                rec = data[6 + i * 12: 6 + (i + 1) * 12]
                if len(rec) < 12:
                    break
                platform, _, _, nid, length, off = struct.unpack(">HHHHHH", rec)
                records.append((platform, nid, length, off))
            for nid in (16, 1):
                for platform in (3, 0, 1):
                    for plat, rid, length, off in records:
                        if plat == platform and rid == nid:
                            raw = data[string_offset + off: string_offset + off + length]
                            if len(raw) < length:
                                continue
                            try:
                                return raw.decode("mac_roman" if platform == 1 else "utf-16-be")
                            except UnicodeDecodeError:
                                continue
            return None
    except (OSError, struct.error):
        return None


# ---------------------------------------------------------------- 缓存（mtime/size 增量）

_CACHE_PATH = DATA_DIR / "fontmgr_cache.json"
_cache: dict = {}


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


def _cached_family(path: str) -> str:
    """按 size+mtime 命中缓存则直接复用家族名（不打开文件）；否则 struct 直读并更新缓存。"""
    key = os.path.normcase(os.path.abspath(path))
    try:
        st = os.stat(path)
        size, mtime = st.st_size, st.st_mtime
    except OSError:
        return ""
    cached = _cache.get(key)
    if cached and cached.get("size") == size and cached.get("mtime") == mtime:
        return cached.get("family") or ""
    family = _read_name_table_family(path) or ""
    _cache[key] = {"family": family, "size": size, "mtime": mtime}
    return family


# ---------------------------------------------------------------- 扫描树

def scan_folder_tree(root: str, errors: list) -> dict | None:
    """递归扫描文件夹为树节点：{path,name,family,is_font,installed,children}。失败返回 None。

    用 os.scandir 枚举（目录项自带 is_dir/is_file，免额外 stat），并走缓存避免重复打开字体。
    """
    try:
        entries = sorted(os.scandir(root), key=lambda e: e.name)
    except OSError as exc:
        errors.append((root, str(exc)))
        return None
    node = {
        "path": root,
        "name": os.path.basename(root) or root,
        "family": "",
        "is_font": False,
        "installed": False,
        "children": [],
    }
    for entry in entries:
        try:
            if entry.is_dir():
                child = scan_folder_tree(entry.path, errors)
                if child is not None:
                    node["children"].append(child)
            elif entry.is_file() and font_io.is_supported(entry.path):
                node["children"].append(font_node(entry.path))
        except OSError:
            continue
    return node


def font_node(path: str) -> dict:
    """单个字体文件的树节点；名称用文件名（文件树视角），家族名放 tooltip。"""
    return {
        "path": path,
        "name": os.path.basename(path),
        "family": _cached_family(path),
        "is_font": True,
        "installed": is_font_installed(path),
        "children": [],
    }
