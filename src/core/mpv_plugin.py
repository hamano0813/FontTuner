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

from core.paths import DATA_DIR

_CACHE_PATH = DATA_DIR / "fontmgr_cache.json"

# 占位符：@CACHE_PATH@（字体缓存 JSON 路径）、@LINK_DIR@（硬链接目录）
_LUA_TEMPLATE = r'''--[[
    拾字 FontTuner 联动脚本：为当前 ASS 字幕自动挂载所需字体。
    由 FontTuner「设置 → MPV 插件 → 写入脚本」生成，请勿手工修改。
    字体缓存: @CACHE_PATH@
    硬链接目录: @LINK_DIR@
]]

local utils = require 'mp.utils'
local msg = require 'mp.msg'
if msg.trace == nil then
    msg.trace = function(...) return mp.log("trace", ...) end
end

local CACHE_PATH = "@CACHE_PATH@"
local LINK_DIR = "@LINK_DIR@"
-- cmd 的 copy/del 只认反斜杠路径，转一份反斜杠副本供命令行用
local LINK_BS = LINK_DIR:gsub("/", "\\")

-- 日志开关：由 FontTuner 设置页控制（false 时脚本不输出任何日志）
local LOG_ENABLE = @LOG_ENABLE@

-- 日志写到脚本同目录 sub-font-tuner.log
local _src = debug.getinfo(1, "S").source or ""
local _script_dir = _src:sub(2):match("^(.*)[/\\][^/\\]+$") or "."
local _log = nil
if LOG_ENABLE then
    _log = io.open(_script_dir .. "/sub-font-tuner.log", "a")
end

local function log(level, text)
    if not LOG_ENABLE then
        return
    end
    msg[level](text)
    if _log then
        _log:write(string.format("%s [%s] %s\n",
            os.date("%Y-%m-%d %H:%M:%S"), level, text))
        _log:flush()
    end
end

local SUB_EXTS = { ["ass"] = true, ["ssa"] = true }
local _processed = false
local _observer = nil

-- ---------- 工具 ----------

-- 设置文件级选项：尊重命令行显式配置（不与之对抗）
local function set_opt(name, value)
    local from_cmd = mp.get_property_bool(string.format(
        "option-info/%s/set-from-commandline", name))
    if from_cmd then
        log("debug", "选项 " .. name .. " 已在命令行显式设置，跳过")
        return
    end
    mp.set_property(string.format("file-local-options/%s", name), value)
    log("trace", "已设 " .. name .. " = " .. tostring(value))
end

-- curl 拉取 URL 内容（Windows 10 1803+ 自带 curl）
local function fetch_url(url)
    local res = utils.subprocess({
        args = { "curl", "-s", "--connect-timeout", "10", "--max-time", "20", url },
        capture_stdout = true,
    })
    if res and res.status == 0 and res.stdout then
        return res.stdout
    end
    if res then
        log("warn", "curl 失败 status=" .. tostring(res.status))
    end
    return nil
end

-- UTF-16LE/BE → UTF-8（纯算术位运算，兼容 mpv 的 Lua 5.1/LuaJIT）
-- 中文字幕常以 UTF-16 保存（PopSub 等老工具），字节流里找不到 [V4+ Styles]/\fn
local function utf16_to_utf8(s, big_endian)
    local out = {}
    local i, n = 1, #s
    local function read16()
        local lo, hi = s:byte(i), s:byte(i + 1)
        i = i + 2
        if big_endian then
            return lo * 256 + hi
        end
        return lo + hi * 256
    end
    local function u8(cp)
        if cp < 0x80 then
            return string.char(cp)
        elseif cp < 0x800 then
            return string.char(0xC0 + math.floor(cp / 0x40),
                               0x80 + cp % 0x40)
        elseif cp < 0x10000 then
            return string.char(0xE0 + math.floor(cp / 0x1000),
                               0x80 + math.floor(cp / 0x40) % 0x40,
                               0x80 + cp % 0x40)
        else
            return string.char(0xF0 + math.floor(cp / 0x40000),
                               0x80 + math.floor(cp / 0x1000) % 0x40,
                               0x80 + math.floor(cp / 0x40) % 0x40,
                               0x80 + cp % 0x40)
        end
    end
    while i + 1 <= n do
        local cp = read16()
        if cp >= 0xD800 and cp <= 0xDBFF and i + 1 <= n then
            local lo = read16()
            if lo >= 0xDC00 and lo <= 0xDFFF then
                cp = 0x10000 + (cp - 0xD800) * 0x400 + (lo - 0xDC00)
            end
        end
        out[#out + 1] = u8(cp)
    end
    return table.concat(out)
end

-- 归一化字幕编码：UTF-16 BOM 转 UTF-8，UTF-8 BOM 剥离
local function normalize_sub_text(s)
    local b1, b2 = s:byte(1), s:byte(2)
    if b1 == 0xFF and b2 == 0xFE then
        return utf16_to_utf8(s:sub(3), false)
    elseif b1 == 0xFE and b2 == 0xFF then
        return utf16_to_utf8(s:sub(3), true)
    elseif b1 == 0xEF and b2 == 0xBB and s:byte(3) == 0xBF then
        return s:sub(4)
    end
    return s
end

-- 读取字幕内容（URL 走 curl，本地路径走 io；读回后归一化编码）
local function get_sub_content(path)
    local c
    if path:match("^https?://") then
        c = fetch_url(path)
    else
        local f = io.open(path, "rb")
        if not f then
            return nil
        end
        c = f:read("*a")
        f:close()
    end
    if c then
        return normalize_sub_text(c)
    end
    return nil
end

-- 清空硬链接目录（启动时先清，避免残留）
-- 注意：cmd del 的通配符只认反斜杠路径（正斜杠会失败），用 LINK_BS 转反斜杠再删
local function clear_link_dir()
    utils.subprocess({
        args = { "cmd", "/c", "del", "/q", LINK_BS .. "\\*" },
        capture_stdout = true,
    })
    log("trace", "已清空链接目录")
end

-- 挂载字体到链接目录：优先硬链接（同卷 NTFS），失败回退复制
-- （SMB/网络卷如 Synology NAS 不支持客户端建硬链接，须复制）
local function mount_font(src, dst)
    local res = utils.subprocess({
        args = { "cmd", "/c", "mklink", "/H", dst, src },
        capture_stdout = true,
    })
    if res and res.status == 0 then
        return "硬链接"
    end
    local c = utils.subprocess({
        args = { "cmd", "/c", "copy", "/y", src, dst },
        capture_stdout = true,
    })
    if c and c.status == 0 then
        return "复制"
    end
    return nil
end

-- ---------- ASS 字体解析 ----------

local function parse_ass_fonts(content)
    local fonts = {}
    local in_styles = false
    local style_col = nil
    local fields = nil
    for line in content:gmatch("[^\r\n]+") do
        line = line:gsub("^%s+", "")
        if line:sub(1, 1) == "[" then
            in_styles = line:lower():find("styles", 1, true) ~= nil
            fields, style_col = nil, nil
        elseif in_styles then
            local low = line:lower()
            if low:find("^format:") then
                fields = {}
                for f in line:sub(8):gmatch("[^,]+") do
                    fields[#fields + 1] = f:gsub("^%s+", ""):gsub("%s+$", "")
                end
                for i, name in ipairs(fields) do
                    if name:lower() == "fontname" then
                        style_col = i
                    end
                end
            elseif low:find("^style:") and style_col and fields then
                local parts = {}
                for p in line:sub(7):gmatch("([^,]+)") do
                    parts[#parts + 1] = p
                end
                local name = parts[style_col]
                if name then
                    name = name:gsub("^%s+", ""):gsub("%s+$", "")
                    if name ~= "" then
                        fonts[name] = true
                    end
                end
            end
        end
        if line:find("\\fn", 1, true) then
            for tag in line:gmatch("\\fn([^\\}]+)") do
                local nm = tag:gsub("^%s+", ""):gsub("%s+$", "")
                if nm ~= "" then
                    fonts[nm] = true
                end
            end
        end
    end
    local out = {}
    for name in pairs(fonts) do
        out[#out + 1] = name
    end
    table.sort(out)
    return out
end

-- ---------- 缓存反查索引 ----------

-- 名称(小写) -> 路径列表
local function build_index()
    local f = io.open(CACHE_PATH, "rb")
    if not f then
        log("warn", "无法读取字体缓存: " .. CACHE_PATH)
        return nil
    end
    local data = utils.parse_json(f:read("*a"))
    f:close()
    if type(data) ~= "table" then
        log("warn", "字体缓存解析失败: " .. CACHE_PATH)
        return nil
    end
    local index = {}
    local add = function(name, path)
        if type(name) == "string" and name ~= "" then
            local key = name:lower()
            if not index[key] then
                index[key] = {}
            end
            index[key][#index[key] + 1] = path
        end
    end
    local link_low = LINK_BS:lower()
    for path, entry in pairs(data) do
        if type(entry) == "table" then
            -- 跳过暂存目录（LINK_DIR）里被缓存到的副本，避免源路径指向刚清空的副本
            if path:lower():sub(1, #link_low) ~= link_low then
                add(entry.win_name, path)
                add(entry.en_name, path)
                add(entry.family, path)
                for _, face in ipairs(entry.faces or {}) do
                    add(face.win_name, path)
                    add(face.en_name, path)
                    add(face.family, path)
                end
            end
        end
    end
    local count = 0
    for _ in pairs(index) do
        count = count + 1
    end
    log("trace", string.format("缓存索引 %d 个名称", count))
    return index
end

-- 匹配字体名 -> 路径列表（精确优先，前缀回退覆盖「家族名+字重」写法）
local function match_font(name, index)
    local key = name:lower()
    if index[key] then
        return index[key]
    end
    local best = {}
    for fam, paths in pairs(index) do
        if #fam < #key and key:sub(1, #fam) == fam then
            for _, p in ipairs(paths) do
                best[#best + 1] = p
            end
        end
    end
    return #best > 0 and best or nil
end

-- ---------- 主流程 ----------

local function find_selected_sub()
    local tracks = mp.get_property_native("track-list")
    if type(tracks) ~= "table" then
        return nil
    end
    for _, t in ipairs(tracks) do
        if t.type == "sub" and t.selected then
            return t["external-filename"] or t["filename"] or t.external_filename or nil
        end
    end
    return mp.get_property("current-tracks/sub/external-filename")
end

local function process()
    if _processed then
        return
    end
    _processed = true

    local sub_path = find_selected_sub()
    if not sub_path then
        log("info", "未找到选中的字幕轨")
        return
    end

    local path_clean = sub_path:gsub("%?.*$", "")
    local ext = path_clean:lower():match("%.([a-z0-9]+)$")
    if not SUB_EXTS[ext] then
        log("info", "非 ASS/SSA（" .. tostring(ext) .. "），跳过字体挂载")
        return
    end

    local content = get_sub_content(sub_path)
    if not content then
        log("warn", "无法获取字幕内容")
        return
    end

    local fonts = parse_ass_fonts(content)
    if #fonts == 0 then
        log("info", "字幕未解析到字体名")
        return
    end
    log("info", "用到的字体: " .. table.concat(fonts, ", "))

    local index = build_index()
    if not index then
        return
    end

    clear_link_dir()
    local linked = 0
    for _, font in ipairs(fonts) do
        local paths = match_font(font, index)
        if not paths then
            log("warn", "字体库未找到: " .. font)
        else
            local mounted = false
            for _, src in ipairs(paths) do
                local base = src:match("[^/\\]+$") or "font.ttf"
                local dst = LINK_BS .. "\\" .. base
                local method = mount_font(src, dst)
                if method then
                    linked = linked + 1
                    log("info", "已挂载(" .. method .. ") " .. font .. " <- " .. src)
                    mounted = true
                    break
                end
            end
            if not mounted then
                log("warn", "挂载失败 " .. font)
            end
        end
    end

    -- 严格使用 ASS 自身样式（否则 mpv 默认 sub-ass-override=yes 会覆盖样式，改用其他字体）
    set_opt("sub-ass-override", "no")
    set_opt("sub-fonts-dir", LINK_DIR)
    log("info", "已设 sub-fonts-dir = " .. LINK_DIR .. "（挂载 " .. linked .. " 个字体）")
end

local function on_tracks_changed()
    if find_selected_sub() then
        process()
        if _observer then
            mp.unobserve_property(_observer)
            _observer = nil
        end
    end
end

mp.add_hook("on_load", 50, function()
    _processed = false
    if _observer then
        mp.unobserve_property(_observer)
        _observer = nil
    end
    _observer = mp.observe_property("track-list", "native", on_tracks_changed)
    on_tracks_changed()
end)
'''


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
        _LUA_TEMPLATE
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
