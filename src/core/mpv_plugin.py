"""MPV 联动：生成并写入 sub-font-tuner.lua 到各 mpv 副本 scripts 目录。

Lua 脚本在 MPV 加载视频时：
1. 从 track-list 取 ASS 字幕 URL → curl 拉取内容 → 解析用到的字体名；
2. 读 fontmgr_cache.json（名称→路径反查索引）；
3. 把匹配到的字体文件硬链接到 LINK_DIR；
4. 设 sub-fonts-dir = LINK_DIR（mpv 重建 libass，字幕重渲染用上新字体）。

写入脚本时把当前运行模式的 fontmgr_cache.json 真实路径与硬链接目录注入模板。
"""

from __future__ import annotations

import os

from core.mpv_plugin_lua import LUA_TEMPLATE
from core.paths import DATA_DIR

_CACHE_PATH = DATA_DIR / "fontmgr_cache.json"


def write_script(
    scripts_dirs: list[str], link_dir: str, log_enable: bool = True,
) -> tuple[bool, str]:
    """把联动 Lua 脚本写入各 mpv 副本 scripts 目录（scripts_dirs 逐个写入）。

    返回 (ok, 消息)：全部成功 ok=True 并列出写入路径；全部失败/未配置目录
    ok=False 并给出原因；部分失败 ok=False 并分别列出成功与失败的目录。
    log_enable 控制脚本是否输出日志（mpv 控制台与脚本同目录 sub-font-tuner.log）。
    """
    if not link_dir:
        return False, "请先设置硬链接目录"
    dirs = [d for d in (scripts_dirs or []) if d]
    if not dirs:
        return False, "请先设置 MPV 脚本目录"
    script = (
        LUA_TEMPLATE
        .replace("@CACHE_PATH@", str(_CACHE_PATH).replace("\\", "/"))
        .replace("@LINK_DIR@", link_dir.replace("\\", "/"))
        .replace("@LOG_ENABLE@", "true" if log_enable else "false")
    )
    written, failed = [], []
    for d in dirs:
        if not os.path.isdir(d):
            failed.append(f"{d}（目录不存在）")
            continue
        path = os.path.join(d, "sub-font-tuner.lua")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(script)
            written.append(path)
        except OSError as exc:
            failed.append(f"{d}（{exc}）")
    if not written:
        return False, "；".join(failed) or "写入失败"
    if failed:
        return False, "部分写入成功：" + "；".join(written) + "；失败：" + "；".join(failed)
    return True, "；".join(written)
