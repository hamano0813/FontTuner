"""应用侧更新助手：读取本地版本、定位并启动 update.exe。

安装态脚本位于 {app}/script/core/，向上逐级查找即可命中 {app}/version 与 {app}/update.exe；
开发态无这些文件：read_version 返回 None，install_dir 返回 None，launch_update 抛
FileNotFoundError。
"""

import subprocess
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent  # core/


def _walk_up() -> list[Path]:
    """从 core/ 逐级向上，返回各祖先目录（含自身）"""
    dirs = [_BASE]
    p = _BASE
    for _ in range(4):
        p = p.parent
        dirs.append(p)
    return dirs


def read_version() -> str | None:
    """读取 version 文件内容；开发态无该文件返回 None"""
    for d in _walk_up():
        ver = d / "version"
        if ver.is_file():
            try:
                return ver.read_text(encoding="utf-8").strip()
            except OSError:
                return None
    return None


def install_dir() -> Path | None:
    """安装目录（含 update.exe 的目录）；找不到返回 None"""
    for d in _walk_up():
        if (d / "update.exe").is_file():
            return d
    return None


def launch_update() -> None:
    """启动 update.exe 执行自动更新，随后退出当前程序（让出文件占用）"""
    base = install_dir() or _BASE
    updater = base / "update.exe"
    if not updater.is_file():
        raise FileNotFoundError("update.exe not found")
    subprocess.Popen(
        [str(updater)],
        cwd=str(updater.parent),
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    sys.exit(0)
