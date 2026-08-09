"""开机自启：写入/删除 HKCU 的 Run 键，入口为引导 exe（FontTuner.exe）。

FontTuner 是「引导 exe + script/*.pyc」的发布形态，开机自启必须指向引导 exe
（{app}/FontTuner.exe），由它再启动 pythonw 跑 main.pyc；直接指向 python 会因
venv 路径/入口差异而失败。安装态才有引导 exe，开发态无，enable 返回 False。
"""

from __future__ import annotations

import sys
import winreg

from core.updater import install_dir

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_NAME = "FontTuner"


def launcher_path() -> str | None:
    """安装态的引导 exe 路径；开发态无则返回 None。"""
    base = install_dir()
    if base is None:
        return None
    exe = base / "FontTuner.exe"
    return str(exe) if exe.is_file() else None


def is_enabled() -> bool:
    """Run 键当前是否写入（自启生效）。"""
    if sys.platform != "win32":
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, _RUN_NAME)
        return True
    except OSError:
        return False


def enable() -> bool:
    """写入 Run 键（值指向引导 exe，带引号）。无引导 exe 或写入失败返回 False。"""
    exe = launcher_path()
    if not exe or sys.platform != "win32":
        return False
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, _RUN_NAME, 0, winreg.REG_SZ, f'"{exe}"')
        return True
    except OSError:
        return False


def disable() -> bool:
    """删除 Run 键；原本就没有视为成功。"""
    if sys.platform != "win32":
        return True
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _RUN_NAME)
    except FileNotFoundError:
        pass
    except OSError:
        return False
    return True
