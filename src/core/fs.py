"""文件系统工具：删除字体文件，优先回收站、无回收站卷回退永久删除（Windows 专用）。

RaiDrive 挂载盘、网络盘等卷没有回收站，FOF_ALLOWUNDO 移入回收站会失败，
此时回退为永久删除并单独返回，供调用方明确提示用户不可恢复。
"""

from __future__ import annotations

import os
import sys

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", wintypes.WORD),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    _FO_DELETE = 0x0003
    _FOF_ALLOWUNDO = 0x0040   # 允许撤销 → 移入回收站
    _FOF_NOCONFIRMATION = 0x0010
    _FOF_SILENT = 0x0004
    _FOF_NOERRORUI = 0x0400

    def _recycle_batch(paths: list[str]) -> list[str]:
        """单个 SHFileOperationW 调用把一批路径移入回收站，返回删除后仍存在的路径。

        无回收站的卷（网络盘/RaiDrive 等）此操作会失败，文件保持原样。
        """
        buffer = "".join(paths) + "\x00\x00"  # 双 null 结尾的多路径缓冲
        op = _SHFILEOPSTRUCTW()
        op.hwnd = None
        op.wFunc = _FO_DELETE
        op.pFrom = buffer
        op.pTo = None
        op.fFlags = _FOF_ALLOWUNDO | _FOF_NOCONFIRMATION | _FOF_SILENT | _FOF_NOERRORUI
        op.fAnyOperationsAborted = False
        ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        # 无法精确获知哪个失败，按「删除后原路径是否还存在」判定
        return [p for p in paths if os.path.exists(p)]


def delete_files(paths: list[str]) -> tuple[list[str], list[str], list[str]]:
    """删除文件：优先移入回收站；回收站不可用的卷回退为永久删除。

    Returns
    -------
    (recycled, permanently_deleted, failed)
      recycled — 已移入回收站，可从回收站恢复
      permanently_deleted — 已永久删除（无回收站回退），不可恢复
      failed — 删除失败（被占用等），文件仍在原路径
    每批最多 10 个，避免单次缓冲过长。
    """
    recycled: list[str] = []
    permanent: list[str] = []
    failed: list[str] = []
    paths = [p for p in paths if p]
    if not paths:
        return recycled, permanent, failed
    if sys.platform != "win32":
        for p in paths:
            try:
                os.remove(p)
                permanent.append(p)
            except OSError:
                failed.append(p)
        return recycled, permanent, failed
    for i in range(0, len(paths), 10):
        still = _recycle_batch(paths[i:i + 10])
        for p in paths[i:i + 10]:
            if p not in still:
                recycled.append(p)
                continue
            # 回收站不可用（无回收站的卷）→ 永久删除；仍失败则确为被占用
            try:
                os.remove(p)
                permanent.append(p)
            except OSError:
                failed.append(p)
    return recycled, permanent, failed
