"""ASS/SSA 字幕字体名提取与批量替换。

字体名有两个来源：
  * 样式行（[V4+ Styles]/[V4 Styles] 的 Style: 行，Fontname 字段，字段序由
    Format: 行定义，缺省按标准第 2 字段）；
  * 事件行里的覆盖标签 {\\fn字体名}（字体名到 \\ 或 } 为止）。
替换时两个来源都写回；行结构（含换行/CRLF）保持不变。带内嵌二进制（[Fonts]）
的字幕解码失败时安全报错，不做破坏性回写。
"""

import re

_STYLE_SECTIONS = ("v4+ styles", "v4 styles", "v4++ styles")
# 内嵌二进制节：解析/替换一律跳过
_SKIP_SECTIONS = ("fonts", "graphics")


def _section(line: str) -> str | None:
    """若该行为节标题则返回小写节名，否则 None。"""
    s = line.strip()
    if s.startswith("[") and s.endswith("]"):
        return s[1:-1].strip().lower()
    return None


def _style_fontname_index(format_line: str) -> int | None:
    """从 Format: 行求 Fontname 字段下标；未声明则按标准位置（第 2 字段=1）。"""
    fields = [f.strip().lower() for f in format_line[len("Format:"):].split(",")]
    return fields.index("fontname") if "fontname" in fields else 1


# ---------------------------------------------------------------- 提取

def extract_font_names(text: str) -> set[str]:
    """提取字幕文本用到的全部字体名（样式 Fontname 字段 + {\\fn...} 覆盖标签）。"""
    names: set[str] = set()
    section = ""
    font_idx: int | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        sec = _section(line)
        if sec is not None:
            section = sec
            font_idx = None
            continue
        if section in _SKIP_SECTIONS:
            continue
        if section in _STYLE_SECTIONS:
            low = line.lower()
            if low.startswith("format:"):
                font_idx = _style_fontname_index(line)
                continue
            if low.startswith("style:") and font_idx is not None:
                parts = line.split(",")
                if len(parts) > font_idx:
                    name = parts[font_idx].strip()
                    if name:
                        names.add(name)
    for m in re.finditer(r"\{[^}]*?\\fn([^}\\]+)", text):
        name = m.group(1).strip()
        if name:
            names.add(name)
    return names


# ---------------------------------------------------------------- 替换

def _replace_fn_tokens(line: str, mapping: dict[str, str]) -> tuple[str, int]:
    """按 mapping 替换行内 {\\fn...} 覆盖标签字体名；返回 (新行, 替换处数)。"""
    count = 0

    def _repl(m):
        nonlocal count
        new = mapping.get(m.group(1).strip())
        if new:
            count += 1
            return "\\fn" + new
        return m.group(0)

    return re.sub(r"\\fn([^}\\]+)", _repl, line), count


def apply_replacements(text: str, repl: dict[str, str]) -> tuple[str, int]:
    """按 repl 批量替换字幕字体名（样式行 Fontname 字段 + {\\fn...} 覆盖标签）。

    Parameters
    ----------
    text : str
        字幕全文。
    repl : dict[str, str]
        旧字体名 -> 新字体名；新名留空或等于旧名会被跳过。

    Returns
    -------
    (new_text, count) — 替换后的文本与替换处数；无有效替换时原样返回 (text, 0)。
    """
    mapping = {old: new for old, new in repl.items() if old and new and old != new}
    if not mapping:
        return text, 0

    out: list[str] = []
    count = 0
    section = ""
    font_idx: int | None = None
    for raw in text.splitlines(keepends=True):
        line = raw.strip()
        if not line:
            out.append(raw)
            continue
        sec = _section(line)
        if sec is not None:
            section = sec
            font_idx = None
            out.append(raw)
            continue
        if section in _SKIP_SECTIONS:
            out.append(raw)
            continue
        new = raw
        if section in _STYLE_SECTIONS and line.lower().startswith("style:"):
            if font_idx is None:
                font_idx = 1  # 未读 Format：按标准位置（Fontname 第 2 字段）
            parts = new.split(",")
            if len(parts) > font_idx:
                old = parts[font_idx].strip()
                if old in mapping:
                    parts[font_idx] = mapping[old]
                    new = ",".join(parts)
                    count += 1
        new, n = _replace_fn_tokens(new, mapping)
        count += n
        out.append(new)
    return "".join(out), count


# ---------------------------------------------------------------- 编码读写

def read_subtitle(path: str) -> tuple[str, str]:
    """读取字幕文本并判定编码，返回 (文本, 编码)。

    编码顺序：UTF-8 BOM → UTF-16 BOM → UTF-8 → GBK。带 [Fonts] 内嵌二进制的
    字幕大概率无法以 UTF-8/GBK 严格解码，此时抛 UnicodeDecodeError 由调用方
    安全报错，避免写回时破坏内嵌数据。
    """
    with open(path, "rb") as f:
        data = f.read()
    if data[:3] == b"\xef\xbb\xbf":
        return data.decode("utf-8-sig"), "utf-8-sig"
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16"), "utf-16"
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("gbk"), "gbk"


def write_subtitle(path: str, text: str, encoding: str) -> None:
    """按原编码写回字幕文本（BOM 随编码自动保留，换行原样保留）。"""
    with open(path, "wb") as f:
        f.write(text.encode(encoding))
