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

from core import font_io, userfont
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


# ---------------------------------------------------------------- 已装检测

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


# ---------------------------------------------------------------- 扫描

# 语言键优先级：简 > 英 > 日 > 繁（「Windows 标准字体名」列默认取用顺序）
_LANG_PRIORITY = ("sc", "en", "jp", "tc")


def _win_lang_key(lang_id: int) -> str | None:
    """Windows 平台语言 ID → 简/繁/日/英 键（中文主语言 0x04 再按子语言细分）。"""
    primary = lang_id & 0x3FF
    if primary == 0x09:      # English（en-US/en-GB/…）
        return "en"
    if primary == 0x11:      # Japanese
        return "jp"
    if primary == 0x04:      # Chinese：子语言 2/3 简体，1/4/5 繁体
        return "sc" if (lang_id >> 10) & 0x3F in (2, 3) else "tc"
    return None


def _mac_lang_key(lang_id: int) -> str | None:
    """Mac 平台语言 ID → 键（仅收录简/繁/日/英，其余返回 None）。"""
    return {0: "en", 11: "jp", 19: "tc", 33: "sc"}.get(lang_id)


_MAC_CODECS = {
    0: "mac_roman", 1: "mac_japanese", 2: "mac_tradchinese", 25: "mac_simpchinese",
    3: "mac_korean", 7: "mac_cyrillic", 21: "mac_thai", 4: "mac_arabic", 5: "mac_hebrew",
}


def _decode_name_raw(platform: int, enc: int, raw: bytes) -> str:
    """按平台/编码解码 name 记录文本。

    Mac(1) 用对应 mac_* 编码（CJK 记录须 mac_japanese/simpchinese 等，mac_roman 会乱码）；
    Windows(3)/Unicode(0) 为 UTF-16（平台 0 enc 4 为小端）。
    """
    if platform == 1:
        return raw.decode(_MAC_CODECS.get(enc, "mac_roman"))
    return raw.decode("utf-16-le" if platform == 0 and enc == 4 else "utf-16-be")


def _read_name_table(path: str, face_index: int = 0) -> tuple[str, str, str, str, str, str, int]:
    """struct 直读 name 表 + maxp 表，返回 (family, subfamily, sub_name, win_name, en_name, version, glyphs)。

    family    — 原逻辑第一匹配（nameID 16→1 × 平台 3→0→1），供注册表/用户字体匹配；
    subfamily — 同逻辑取子家族名（nameID 17→2），供 TTC face 展示 / 安装命名；
    sub_name  — 本地化子家族名：与 win_name 同语言的子家族名（nameID 17→2），
                供字体管理树「子家族名」列与 Windows 标准字体名同语言展示，缺则回退 subfamily；
    win_name  — Windows 标准字体名列展示名：按 简→英→日→繁 优先级取同语言
                家族名(nameID 1)，同语言缺则回退首选家族名(nameID 16)；
                全缺回退 family；
    en_name   — 英文家族名（语言 en，nameID 16→1），作下拉框隐藏匹配词，无则回退 family；
    version   — 版本字符串（nameID 5）：按 英→简→日→繁 优先级取同语言版本串，
                截断到首个分号（去掉厂商/字体工具尾巴）；全缺为空；
    glyphs    — 字形数（maxp 表 numGlyphs），读取失败为 0。
    TTC 取第 face_index 个子字体（默认 0）；失败返回 ("", "", "", "", "", "", 0)。
    """
    try:
        with open(path, "rb") as f:
            magic = f.read(4)
            base = 0
            if magic == b"ttcf":
                f.read(4)  # version
                num_fonts = struct.unpack(">I", f.read(4))[0]
                if face_index < 0 or face_index >= num_fonts:
                    return "", "", "", "", "", "", 0
                # 'ttcf'(4) + version(4) + numFonts(4) 之后是 numFonts 个 32 位子字体偏移
                f.seek(12 + 4 * face_index)
                base = struct.unpack(">I", f.read(4))[0]
                f.seek(base)
                magic = f.read(4)
            if magic not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
                return "", "", "", "", "", "", 0
            header = f.read(8)  # numTables/searchRange/entrySelector/rangeShift
            if len(header) < 8:
                return "", "", "", "", "", "", 0
            num_tables = struct.unpack(">H", header[0:2])[0]
            name_off = name_len = maxp_off = None
            for _ in range(num_tables):
                rec = f.read(16)
                if len(rec) < 16:
                    return "", "", "", "", "", "", 0
                tag = rec[0:4]
                offset, length = struct.unpack(">II", rec[8:16])
                if tag == b"name":
                    name_off, name_len = offset, length
                elif tag == b"maxp":
                    maxp_off = offset
            if name_off is None:
                return "", "", "", "", "", "", 0
            # TTC 子字体的表偏移是绝对文件偏移（实测 fontTools 与 Windows 字体均如此），
            # base 只用于定位 sfnt 头，读表数据直接用 name_off / maxp_off
            f.seek(name_off)
            data = f.read(name_len)
            if len(data) < 6:
                return "", "", "", "", "", "", 0
            # 字形数：maxp 表 offset 4 处的 2 字节 numGlyphs（TTF/OTF 均为此布局）
            glyphs = 0
            if maxp_off is not None:
                f.seek(maxp_off)
                maxp = f.read(6)
                if len(maxp) >= 6:
                    glyphs = struct.unpack(">H", maxp[4:6])[0]
            count = struct.unpack(">H", data[2:4])[0]
            string_offset = struct.unpack(">H", data[4:6])[0]
            records = []
            for i in range(count):
                rec = data[6 + i * 12: 6 + (i + 1) * 12]
                if len(rec) < 12:
                    break
                platform, enc, lang_id, nid, length, off = struct.unpack(">HHHHHH", rec)
                records.append((platform, enc, lang_id, nid, length, off))
    except (OSError, struct.error):
        return "", "", "", "", "", "", 0

    texts: dict[tuple, str] = {}   # (platform, lang_id, nid) -> 首个文本
    ordered: list[tuple] = []      # 首次出现顺序
    for platform, enc, lang_id, nid, length, off in records:
        if nid not in (1, 2, 5, 16, 17):  # 5=版本字符串，也参与语言分桶
            continue
        raw = data[string_offset + off: string_offset + off + length]
        if len(raw) < length:
            continue
        try:
            text = _decode_name_raw(platform, enc, raw).strip()
        except (UnicodeDecodeError, LookupError):
            continue
        if not text:
            continue
        key = (platform, lang_id, nid)
        if key not in texts:
            texts[key] = text
            ordered.append(key)

    def _first_match(*nids: int) -> str:
        """原逻辑第一匹配（nameID 优先级 × 平台 3→0→1，文件内首个）。"""
        for nid in nids:
            for platform in (3, 0, 1):
                for plat, lang_id, nid2 in ordered:
                    if plat == platform and nid2 == nid:
                        return texts[(plat, lang_id, nid2)]
        return ""

    family = _first_match(16, 1)
    subfamily = _first_match(17, 2)

    # 按语言收集：best_1=家族名(1)，best_2=子家族名(2)，best_16=首选家族名(16)，
    # best_17=首选子家族名(17)，best_5=版本串(5)。
    # 同语言多平台记录时优先 Windows(3)，其次 Mac(1)/Unicode(0) 兜底，
    # 避免 Mac 记录（尤其 CJK 编码差异）覆盖 Windows 的干净文本。
    _plat_priority = {3: 0, 1: 1, 0: 2}
    _buckets: dict[int, dict[str, tuple[int, str]]] = {1: {}, 2: {}, 5: {}, 16: {}, 17: {}}
    for platform, lang_id, nid in ordered:
        if nid not in _buckets:
            continue
        lk = _win_lang_key(lang_id) if platform == 3 else (
            _mac_lang_key(lang_id) if platform == 1 else None)
        if lk is None:
            continue
        bucket = _buckets[nid]
        cur = bucket.get(lk)
        if cur is None or _plat_priority[platform] < cur[0]:
            bucket[lk] = (_plat_priority[platform], texts[(platform, lang_id, nid)])
    best_1 = {k: v[1] for k, v in _buckets[1].items()}
    best_2 = {k: v[1] for k, v in _buckets[2].items()}
    best_5 = {k: v[1] for k, v in _buckets[5].items()}
    best_16 = {k: v[1] for k, v in _buckets[16].items()}
    best_17 = {k: v[1] for k, v in _buckets[17].items()}

    # version：版本字符串按 英→简→日→繁 优先级取（与 win_name 的 简→英→日→繁 不同），
    # 截断到首个分号去掉厂商/字体工具尾巴（如 "Version 2.00;FontCreator 11.5..."）
    version = ""
    for lk in ("en", "sc", "jp", "tc"):
        if lk in best_5:
            version = best_5[lk].split(";", 1)[0].strip()
            break

    # win_name：简→英→日→繁，取同语言家族名(nameID 1)，缺则回退首选家族名(nameID 16)
    win_name = ""
    win_lang = None
    for lk in _LANG_PRIORITY:
        if lk in best_1:
            win_name, win_lang = best_1[lk], lk
            break
        if lk in best_16:
            win_name, win_lang = best_16[lk], lk
            break
    if not win_name:  # 回退：文件里第一个家族名
        win_name = family

    # sub_name：与 win_name 同语言的子家族名（首选子家族名 17 → 子家族名 2），
    # 与「Windows 标准字体名」列同语言展示；同语言缺则回退 subfamily（首个匹配）
    sub_name = ""
    if win_lang is not None:
        sub_name = best_17.get(win_lang) or best_2.get(win_lang) or ""
    if not sub_name:
        sub_name = subfamily

    # en_name：英文家族名（语言 en，nameID 16→1），作下拉框隐藏匹配词；无则回退 family
    en_name = best_16.get("en") or best_1.get("en") or ""
    if not en_name:
        en_name = family
    return family, subfamily, sub_name, win_name, en_name, version, glyphs


# ---------------------------------------------------------------- 缓存（mtime/size 增量）

_CACHE_PATH = DATA_DIR / "fontmgr_cache.json"
# 缓存结构版本：win_name 语义（家族名优先、语言优先级 简英日繁）变更时 +1，使旧缓存自动失效重读
_CACHE_VERSION = 7
_cache: dict = {}
# 硬重扫标志：重新扫描按钮置位，使名称读取跳过 mtime/size 缓存，
# 对已存在的文件也强制重读名称表，并回写刷新缓存条目
_hard_rescan = False


def set_hard_rescan(flag: bool) -> None:
    global _hard_rescan
    _hard_rescan = bool(flag)


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


def font_style(path: str) -> tuple[int, bool]:
    """字体的真实字重（OS/2 usWeightClass）与斜体标志。

    直接读字体二进制，不依赖子家族名的厂商写法差异（Hairline/Semi Bold/Demi…），
    供预览按真实字重建 QFont，保证同家族多字重文件能稳定切换渲染 face。
    读取失败回落 (400, False)；TTC/OTC 取第 1 个 face。
    """
    try:
        from fontTools.ttLib import TTFont
        font = TTFont(path, fontNumber=0, lazy=True)
        try:
            os2 = font.get("OS/2")
            head = font.get("head")
            weight = os2.usWeightClass if os2 is not None else 400
            italic = bool(head is not None and (head.macStyle & 0x02))
            if os2 is not None:
                italic = italic or bool(os2.fsSelection & 0x0001)
            return weight, italic
        finally:
            font.close()
    except Exception:
        return 400, False


def _cached_names(path: str) -> tuple[str, str, str, str, str, str, int]:
    """按 size+mtime 命中缓存则直接复用名称（不打开文件）；否则 struct 直读并更新缓存。

    返回 (family, subfamily, sub_name, win_name, en_name, version, glyphs)，与 _read_name_table 顺序一致。
    旧缓存条目缺 win_name/en_name/version/glyphs 时回退 family / 空值。
    """
    key = os.path.normcase(os.path.abspath(path))
    try:
        st = os.stat(path)
        size, mtime = st.st_size, st.st_mtime
    except OSError:
        return "", "", "", "", "", "", 0
    cached = _cache.get(key)
    if (not _hard_rescan and cached and cached.get("v") == _CACHE_VERSION
            and cached.get("size") == size and cached.get("mtime") == mtime):
        family = cached.get("family") or ""
        subfamily = cached.get("subfamily") or ""
        sub_name = cached.get("sub_name") or subfamily
        win_name = cached.get("win_name")
        en_name = cached.get("en_name")
        version = cached.get("version") or ""
        glyphs = cached.get("glyphs") or 0
        return family, subfamily, sub_name, (
            win_name if win_name is not None else family), (
            en_name if en_name is not None else family), version, glyphs
    family, subfamily, sub_name, win_name, en_name, version, glyphs = _read_name_table(path)
    _cache[key] = {"v": _CACHE_VERSION, "family": family, "subfamily": subfamily,
                   "sub_name": sub_name,
                   "win_name": win_name, "en_name": en_name,
                   "version": version, "glyphs": glyphs,
                   "size": size, "mtime": mtime}
    return family, subfamily, sub_name, win_name, en_name, version, glyphs


def _cached_faces(path: str) -> list[dict]:
    """读取 TTC/OTC 全部 face 的名称列表（按 size+mtime+版本 缓存）。

    每个 face：{family, subfamily, win_name, en_name, version, glyphs}；读取失败返回 []。
    """
    key = os.path.normcase(os.path.abspath(path))
    try:
        st = os.stat(path)
        size, mtime = st.st_size, st.st_mtime
    except OSError:
        return []
    cached = _cache.get(key)
    if (not _hard_rescan and cached and cached.get("v") == _CACHE_VERSION
            and cached.get("size") == size and cached.get("mtime") == mtime
            and isinstance(cached.get("faces"), list)):
        return cached["faces"]
    num = 0
    try:
        with open(path, "rb") as f:
            if f.read(4) != b"ttcf":
                return []
            f.read(4)  # version
            num = struct.unpack(">I", f.read(4))[0]
    except (OSError, struct.error):
        return []
    faces = []
    for i in range(num):
        family, subfamily, sub_name, win_name, en_name, version, glyphs = _read_name_table(path, i)
        faces.append({"family": family, "subfamily": subfamily, "sub_name": sub_name,
                      "win_name": win_name, "en_name": en_name,
                      "version": version, "glyphs": glyphs})
    entry = _cache.get(key) or {}
    entry["v"] = _CACHE_VERSION
    entry["size"] = size
    entry["mtime"] = mtime
    entry["faces"] = faces
    _cache[key] = entry
    return faces


# ---------------------------------------------------------------- 扫描树

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


_COLLECTION_EXTENSIONS = (".ttc", ".otc")


def _is_collection(path: str) -> bool:
    return path.lower().endswith(_COLLECTION_EXTENSIONS)


# ---------------------------------------------------------------- 全局已装字体枚举

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
            if _is_collection(path):
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
    if _is_collection(path):
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
