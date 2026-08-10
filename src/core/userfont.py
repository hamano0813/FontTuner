"""当前用户字体安装/卸载：复制到用户字体目录 + HKCU 注册表 + WM_FONTCHANGE。

会话级注册（font_register）只对 GDI 应用可见，DirectWrite 应用（Windows Terminal、
VS Code 等）看不到。要让这些应用能枚举字体，必须走「当前用户安装」：
把字体复制到 %LOCALAPPDATA%\\Microsoft\\Windows\\Fonts，并在
HKCU\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Fonts 写一条
「家族名 (TrueType)」= 完整路径。卸载按反向顺序：删注册表值 → 广播 →
删文件（带重试；仍被占用则 MoveFileEx 延迟到重启删除，免安全模式）。

检测「某字体已安装到当前用户」按家族名比对 HKCU 注册表（值名家族 + 数据指向
用户字体目录），不按文件是否存在，避免孤文件误报；复制重名时目标文件改名，
检测不受影响。
"""

from __future__ import annotations

import ctypes
import os
import shutil
import time
import winreg

_KEY = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"

_HWND_BROADCAST = 0xFFFF
_WM_FONTCHANGE = 0x001D
_MOVEFILE_DELAY_UNTIL_REBOOT = 0x0004

_user32 = ctypes.WinDLL("user32")
_kernel32 = ctypes.WinDLL("kernel32")
_kernel32.MoveFileExW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
_kernel32.MoveFileExW.restype = ctypes.c_int

# 已安装缓存：小写家族名 -> 注册表指向的字体文件全路径。安装/卸载/重扫时刷新。
_cache: dict[str, str] | None = None


def user_fonts_dir() -> str:
    """当前用户字体目录（Windows 10 1809+ 的「为当前用户安装」落地位置）。"""
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")


def _strip_suffix(name: str) -> str:
    """注册表值名去掉「 (TrueType)/(OpenType)」后缀，得到家族名。"""
    for suffix in (" (OpenType)", " (TrueType)"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _under_user_dir(path: str) -> bool:
    d = os.path.normcase(user_fonts_dir())
    p = os.path.normcase(path)
    return p == d or p.startswith(d + os.sep)


def _notify_font_change() -> None:
    """广播 WM_FONTCHANGE，让已运行的应用刷新字体列表。"""
    _user32.PostMessageW(_HWND_BROADCAST, _WM_FONTCHANGE, 0, 0)


# ---------------------------------------------------------------- 缓存

def refresh_user_font_cache() -> None:
    """重建「已安装到当前用户」家族缓存（读 HKCU 注册表一次）。"""
    global _cache
    _cache = {}
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY)
    except OSError:
        return
    try:
        for i in range(winreg.QueryInfoKey(key)[1]):
            name, data, _ = winreg.EnumValue(key, i)
            if not isinstance(data, str) or not data.strip():
                continue
            if not _under_user_dir(data):
                continue
            family = _strip_suffix(name)
            if family:
                _cache[family.lower()] = data
    finally:
        key.Close()


def installed_user_families() -> set[str]:
    """已安装到当前用户的家族名集合（小写），供扫描检测。"""
    if _cache is None:
        refresh_user_font_cache()
    return set(_cache or {})


def find_user_font(family: str) -> str:
    """按家族名找已安装到当前用户的字体文件路径；未安装返回 ''。"""
    if _cache is None:
        refresh_user_font_cache()
    return (_cache or {}).get(family.lower(), "")


# ---------------------------------------------------------------- 安装

def _unique_target(library_path: str) -> str:
    """用户字体目录里的目标路径；同名冲突时加数字后缀（不影响家族名注册）。"""
    name, ext = os.path.splitext(os.path.basename(library_path))
    target = os.path.join(user_fonts_dir(), name + ext)
    n = 2
    while os.path.exists(target):
        target = os.path.join(user_fonts_dir(), f"{name}-{n}{ext}")
        n += 1
    return target


def install_to_user(library_path: str, family: str) -> tuple[bool, str, str]:
    """把字体安装到当前用户：复制 + 注册表 + 广播。

    Returns
    -------
    (ok, error, installed_path) — 已装过则幂等返回成功；失败返回 False 与原因。
    """
    if not os.path.isfile(library_path):
        return False, "字体文件不存在", ""
    if not family.strip():
        return False, "无法读取字体家族名", ""
    existing = find_user_font(family)
    if existing and os.path.isfile(existing):
        return True, "", existing  # 幂等：已安装
    target = _unique_target(library_path)
    try:
        os.makedirs(user_fonts_dir(), exist_ok=True)
        shutil.copy2(library_path, target)
    except OSError as exc:
        return False, f"复制失败：{exc}", ""
    ext = os.path.splitext(library_path)[1].lower()
    value_name = f"{family} (OpenType)" if ext in (".otf", ".otc") else f"{family} (TrueType)"
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, _KEY)
        try:
            winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, target)
        finally:
            key.Close()
    except OSError as exc:
        try:
            os.remove(target)  # 注册表失败回滚复制
        except OSError:
            pass
        return False, f"注册表写入失败：{exc}", ""
    _notify_font_change()
    refresh_user_font_cache()
    return True, "", target


# ---------------------------------------------------------------- 卸载

def _schedule_delete_on_reboot(path: str) -> bool:
    """把文件标记为重启时删除（被占用时的兜底，免安全模式）。"""
    return bool(_kernel32.MoveFileExW(path, None, _MOVEFILE_DELAY_UNTIL_REBOOT))


def _delete_with_retry(path: str) -> tuple[bool, bool]:
    """重试删除文件。返回 (已删除, 已安排重启删除)。"""
    for _ in range(3):
        try:
            os.remove(path)
            return True, False
        except OSError:
            time.sleep(0.3)
    return False, _schedule_delete_on_reboot(path)


def uninstall_from_user(family: str) -> tuple[bool, str, str]:
    """取消当前用户安装：删注册表值 → 广播 → 删文件（重试/延迟重启）。

    Returns
    -------
    (ok, status, detail)
      status: "deleted" 已删文件 / "deferred" 注册表已删、文件重启后清理 /
              "locked" 文件删不掉也未安排（罕见） / "failed" 注册表操作失败
    """
    value_name = None
    target = None
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY, 0, winreg.KEY_READ | winreg.KEY_WRITE)
    except OSError as exc:
        return False, "failed", f"打开注册表失败：{exc}"
    try:
        for i in range(winreg.QueryInfoKey(key)[1]):
            name, data, _ = winreg.EnumValue(key, i)
            if not isinstance(data, str) or not data.strip():
                continue
            if _strip_suffix(name).lower() != family.lower():
                continue
            if not _under_user_dir(data):
                continue
            value_name, target = name, data
            winreg.DeleteValue(key, name)
            break
    except OSError as exc:
        return False, "failed", f"删除注册表值失败：{exc}"
    finally:
        key.Close()

    if target is None:
        return True, "deleted", ""  # 未找到登记，视为已完成（幂等）
    _notify_font_change()
    deleted, deferred = _delete_with_retry(target)
    refresh_user_font_cache()
    if deleted:
        return True, "deleted", ""
    if deferred:
        return True, "deferred", target
    return True, "locked", target
