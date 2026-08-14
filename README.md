# 拾字 FontTuner

[![Python](https://img.shields.io/badge/Python-%E2%89%A53.14-blue?logo=python&style=flat&labelColor=013243)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-6.7%2B-green?logo=qt&style=flat&labelColor=013243)](https://doc.qt.io/qtforpython-6/)
[![uv](https://img.shields.io/badge/uv-0.6%2B-261230?style=flat&labelColor=013243)](https://docs.astral.sh/uv/)
[![Inno Setup](https://img.shields.io/badge/Inno%20Setup-6.4%2B-blue?style=flat&labelColor=013243)](https://jrsoftware.org/isinfo.php)
[![Windows](https://img.shields.io/badge/Windows-10%2B-00A4EF?logo=windows&style=flat&labelColor=013243)](https://www.microsoft.com/windows)
[![GPLv3](https://img.shields.io/badge/License-GPLv3-red?logo=gnu&style=flat&labelColor=013243)](LICENSE)

> 字体元数据编辑 · TTC/OTC 解包打包 · 字体管理 · MPV 字幕字体联动 —— 面向简体 / 繁体 / 日文 / 英文四语言的专业字体工具。

拾字 FontTuner 是一个基于 PySide6 + [PySide6-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)（qfw）的 Windows 桌面应用。它围绕字体文件（`.ttf` / `.otf` / `.ttc` / `.otc`）的 **name 表元数据** 提供批量编辑能力，并附带 TTC/OTC 解包打包、字体注册管理与 MPV 字幕字体联动。

---

## 功能一览

| 页面 | 说明 |
| --- | --- |
| **字体管理** | 树形浏览字体库文件夹，五列展示（字体文件、Windows 标准字体名、子家族名、字形数、版本），勾选即注册到 Windows（当前会话有效），系统已装字体灰显标记；目录级三态勾选、按名称/家族名筛选、**检查重复**、保存/恢复选中、底部多语言预览，右键可**安装到当前用户**、发送到字体编辑、删除字体文件；**字幕适配**：把 `.ass`/`.ssa` 字幕用到的字体名批量替换为字体库字体 |
| **解包打包** | `.ttc`/`.otc` 集合 → 拆成独立 `.ttf`/`.otf`；多个 `.ttf`/`.otf` → 合并成 `.ttc`/`.otc`（格式可选 自动/ttc/otc）。按字体内名称命名（首选家族名-首选子家族名），重名自动加序号 |
| **字体编辑** | 树形表格：每个字体一个父节点，简/繁/日/英四个语言子节点；父行编辑字重（1–1000 数值）、字宽（9 档）、斜体、字形数与模板、重命名模板列，子行编辑对应语言 name 表 20 个字段（家族名、子家族名、唯一标识、全名、版权、厂商、许可等）、临时名称、字符集，勾选「保存」的语言才写入 |
| **信息模板** | 维护字体信息字段集 + 字重/字宽/斜体翻译映射表（JSON 持久化），在「字体编辑」页一键应用到选中/全部字体；支持 `{weight}`、`{family_sc}` 等占位符，解析为空文本时自动删除前导空格；每模板可携带**重命名模板**（空 = 应用模板时不重命名） |
| **设置** | 主题模式、预览文字与字号、开机自动启动、自动恢复选中、关闭到系统托盘、MPV 插件联动、关于与检查更新 |

### 字幕字体适配细节

- 从字幕的 **Style 行**（`[V4+ Styles]` / `[V4 Styles]` 的 Fontname 字段）与事件行的 **`{\fn字体名}`** 覆盖标签提取字体名，跨文件去重。
- 每个字体名一行，右侧下拉从**当前字体库**选择替换字体：与字体库完全匹配的自动预选，未匹配的留空（= 不替换）；下拉支持输入匹配（中文名或英文系统名，忽略大小写）。
- 确定后批量替换写回原文件，保留原编码（UTF-8 / UTF-16 BOM、GBK）与换行，`[Fonts]` 内嵌二进制节不受影响。

### 字体编辑细节

- **树形结构**：每个字体一个父节点，简/繁/日/英四个语言子节点；父行编辑字重（1–1000 数值直编）、字宽（9 档枚举下拉）、斜体勾选、字形数（只读）与「模板」「重命名模板」列，子行编辑该语言的 name 表 20 个字段、临时名称、字符集与保存勾选。
- **语言开关**：顶部简/繁/日/英四个开关，单独显示/隐藏各父节点下对应语言子行；「全部字段」开关展开非常用 name 字段列。
- **保存勾选**：每个语言子行一个「保存」复选框（含语言标签），勾选才写入该语言记录；勾选但全空不新建，未勾选且字体中存在的语言记录保存时删除。
- **占位符解析**：「解析」按钮（及模板应用、重命名）把 `{weight}`、`{width}`、`{italic}`、`{weight_num}`、`{width_num}`、`{family_xx}`、`{subfamily_xx}`、`{preferred_family_xx}`、`{version_xx}`、`{name_xx}`、`{charset_xx}` 等动态变量展开为实际文本；`xx` 可替换为 `sc`/`tc`/`jp`/`en`。保存纯写入、不解析占位符——未解析的 `{...}` 原样写入，需先点「解析」再保存。
- **家族名原样保存**：家族名（nameID 1）按编辑值原样写回，不再按字重/字宽自动拼接；不自动生成子家族名（子家族名 2 由模板字段或手动填写）。
- **重命名模板列**：字体编辑页的「重命名模板」列跟随信息模板；空 = 应用模板时不重命名，填写 = 由「解析」按钮一并按占位符展开为文件名。

### MPV 字幕字体联动

无需把字体库安装进系统，让 mpv / Jellyfin 播放时按需挂载字幕用到的字体：

1. 在**设置 → MPV 插件**配置**字体暂存目录**（建议与字体库同盘）与 mpv / Jellyfin 的 **scripts 目录**，点「写入脚本」生成联动 Lua 脚本。
2. 播放视频时脚本自动：从 `track-list` 取当前 ASS 字幕（Jellyfin 流式下发的 URL 亦可）→ 解析用到的字体名 → 按字体库缓存反查文件路径 → **挂载**（硬链接优先，SMB / 网络卷自动回退复制）到暂存目录 → 设置 `sub-fonts-dir` 并强制 `sub-ass-override=no`（严格按 ASS 自身样式渲染）。
3. 每次启动先清空暂存目录，只保留当前字幕用到的字体；不占用系统字体注册，卸载即清。

---

## 快速上手

1. 在**字体管理**页勾选目标字体（或按目录三态勾选），即可注册到 Windows，系统已装字体自动灰显；需要批量改字幕字体时，用「字幕适配」选择 `.ass`/`.ssa` 文件。
2. 用**解包打包**页拆分 `.ttc`/`.otc` 集合为独立字体，或在编辑后合并回集合。
3. 在**字体编辑**页批量修改 name 表元数据，配合**信息模板**一键套用预设字段集与重命名模板。
4. 在**信息模板**页编辑模板：为字重/字宽/斜体配置简繁日英映射表（「文本翻译」页签），再按语言 Tab 填各字段。
5. 在**设置**页配置主题、预览文字与字号、开机自启、自动恢复选中，以及 MPV 字幕字体联动。

---

## 下载与使用

从 Releases 或本地构建产物获取安装包 `FontTuner-<版本>-x64.zip`，解压后运行其中的安装程序即可。

安装过程**需要联网**：安装器会经 uv 自动下载 Python 环境并同步依赖，视网络情况等待几分钟。

> 打包安装后，数据文件 `data/templates.json`、`data/fontmgr_cache.json` 与 `config.json` 存于 `%APPDATA%\FontTuner`（安装根不可写时回落），首次运行按默认值自动生成。

---

## 技术栈

- [PySide6](https://doc.qt.io/qtforpython/)（Qt 6 GUI）
- [PySide6-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)（Fluent 设计组件）
- [fontTools](https://github.com/fonttools/fonttools)（字体解析 / TTC 打包解包）

---

## 支持

“我有一个很好的想法，但我的token不够了”

</br>

<!-- markdownlint-disable-next-line MD033 -->
<img src="res/img/bill.png" width="400" alt="收款码">

---

## 许可

[GPL-3.0](LICENSE) © 2026 拾字 FontTuner
