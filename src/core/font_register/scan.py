"""文件夹扫描树：递归枚举目录下的字体文件为树节点，供字体管理页展示。"""

from __future__ import annotations

import os

from core import font_io, userfont
from core.font_register.cache import _cached_faces, _cached_names
from core.font_register.installed import is_font_installed


def scan_folder_tree(root: str, errors: list) -> dict | None:
    """递归扫描文件夹为树节点：{path,name,family,win_name,en_name,is_font,is_font_face,installed,children}。失败返回 None。

    用 os.scandir 枚举（目录项自带 is_dir/is_file，免额外 stat），并走缓存避免重复打开字体。
    """
    try:
        def _dir_first(e):
            # 文件夹排最前，再按名称排序（is_dir 失败按文件处理）
            try:
                return (not e.is_dir(), e.name.casefold())
            except OSError:
                return (1, e.name.casefold())
        entries = sorted(os.scandir(root), key=_dir_first)
    except OSError as exc:
        errors.append((root, str(exc)))
        return None
    node = {
        "path": root,
        "name": os.path.basename(root) or root,
        "family": "",
        "sub_name": "",
        "win_name": "",
        "en_name": "",
        "version": "",
        "glyphs": 0,
        "is_font": False,
        "is_font_face": False,
        "installed": False,
        "installed_user_path": "",
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


def _face_node(face: dict, index: int) -> dict:
    """TTC/OTC 内的一个 face 子节点：仅展示，不可勾选（只能勾选整个集合文件）。"""
    family = face.get("family") or ""
    subfamily = face.get("subfamily") or ""
    display = f"{family}-{subfamily}" if family and subfamily else (family or subfamily)
    return {
        "path": "",
        "name": display or f"face{index + 1}",
        "family": family,
        "sub_name": face.get("sub_name") or "",
        "win_name": face.get("win_name") or "",
        "en_name": face.get("en_name") or "",
        "version": face.get("version") or "",
        "glyphs": face.get("glyphs") or 0,
        "is_font": False,
        "is_font_face": True,
        "installed": False,
        "installed_user_path": "",
        "children": [],
    }


def font_node(path: str) -> dict:
    """单个字体文件的树节点；文件名作第 1 列，win_name（Windows 标准字体名）作第 2 列。

    TTC/OTC 整体作为一个可勾选节点，其下展开各 face 子节点（不可勾选，仅展示）。
    """
    node: dict = {
        "path": path,
        "name": os.path.basename(path),
        "family": "",
        "subfamily": "",
        "sub_name": "",
        "win_name": "",
        "en_name": "",
        "version": "",
        "glyphs": 0,
        "is_font": True,
        "is_font_face": False,
        "installed": is_font_installed(path),
        "installed_user_path": "",
        "children": [],
    }
    if font_io.is_collection(path):
        faces = _cached_faces(path)
        node["children"] = [_face_node(f, i) for i, f in enumerate(faces)]
        if faces:
            node["family"] = faces[0]["family"]
            node["subfamily"] = faces[0].get("subfamily") or ""
            node["sub_name"] = faces[0].get("sub_name") or ""
            node["win_name"] = faces[0]["win_name"]
            node["en_name"] = faces[0]["en_name"]
            node["version"] = faces[0].get("version") or ""
            node["glyphs"] = faces[0].get("glyphs") or 0
    else:
        family, subfamily, sub_name, win_name, en_name, version, glyphs = _cached_names(path)
        node["family"], node["subfamily"] = family, subfamily
        node["sub_name"] = sub_name
        node["win_name"], node["en_name"] = win_name, en_name
        node["version"], node["glyphs"] = version, glyphs
    # 已安装到当前用户检测：先按字重名（family + subfamily，对应「家族名 字重」注册表值名，
    # 常规字重不带后缀），命中则精确到本字重；未命中再按 family（英文家族名），仍未命中按
    # win_name（本地化显示名）。Windows 注册表值名用本地化名（如「方正悠黑_GBK 503L」），
    # 纯按英文 family 会漏检中文名字体，导致真已安装却显示「未安装」；win_name 兜底命中。
    family = node.get("family") or ""
    subfamily = node.get("subfamily") or ""
    if family:
        if subfamily and subfamily.lower() != "regular":
            node["installed_user_path"] = userfont.find_user_font(f"{family} {subfamily}")
        if not node["installed_user_path"]:
            node["installed_user_path"] = userfont.find_user_font(family)
    if not node["installed_user_path"] and node["win_name"] and node["win_name"] != family:
        node["installed_user_path"] = userfont.find_user_font(node["win_name"])
    return node
