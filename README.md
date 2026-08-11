# 拾字 FontTuner

[![Python](https://img.shields.io/badge/Python-%E2%89%A53.14-blue?logo=python&style=flat&labelColor=013243)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-6.7%2B-green?logo=qt&style=flat&labelColor=013243)](https://doc.qt.io/qtforpython-6/)
[![uv](https://img.shields.io/badge/uv-0.6%2B-261230?style=flat&labelColor=013243)](https://docs.astral.sh/uv/)
[![Inno Setup](https://img.shields.io/badge/Inno%20Setup-6.4%2B-blue?style=flat&labelColor=013243)](https://jrsoftware.org/isinfo.php)
[![Windows](https://img.shields.io/badge/Windows-10%2B-00A4EF?logo=windows&style=flat&labelColor=013243)](https://www.microsoft.com/windows)
[![GPLv3](https://img.shields.io/badge/License-GPLv3-red?logo=gnu&style=flat&labelColor=013243)](LICENSE)

> 字体元数据编辑 · TTC/OTC 解包打包 · 字体管理 · MPV 字幕字体联动 —— 面向简体 / 繁体 / 日文 / 英文四语言的专业字体工具。

拾字 FontTuner 是一个基于 PySide6 + [PySide6-Fluent-Widgets](https://github.com/zhiyiYo/PySide6-Fluent-Widgets)（qfw）的 Windows 桌面应用。它围绕字体文件（`.ttf` / `.otf` / `.ttc` / `.otc`）的 **name 表元数据** 提供批量编辑能力，并附带 TTC/OTC 解包打包、字体注册管理与 MPV 字幕字体联动。

---

## 功能一览

| 页面 | 说明 |
| --- | --- |
| **字体管理** | 树形浏览字体库文件夹，两列展示（文件名 + Windows 标准字体名，简→英→日→繁优先取用），勾选即注册到 Windows（当前会话有效），系统已装字体灰显标记；目录级三态勾选、按名称/家族名筛选、底部多语言预览；**字幕适配**：把 `.ass`/`.ssa` 字幕用到的字体名批量替换为字体库字体 |
| **解包打包** | `.ttc`/`.otc` 集合 → 拆成独立 `.ttf`/`.otf`；多个 `.ttf`/`.otf` → 合并成 `.ttc`/`.otc`。按字体内名称命名（首选家族名-首选子家族名），重名自动加序号 |
| **字体编辑** | 批量编辑 name 表 20 个字段 × 简/繁/日/英四种语言：家族名、子家族名、唯一标识、全名、字体名、版权、厂商、许可等；字重/字宽/斜体直接编辑；临时名称/字符集占位列；重命名模板列（跟随信息模板，空 = 不重命名） |
| **信息模板** | 维护字体信息字段集（JSON 持久化），在「字体编辑」页一键应用到选中/全部字体；支持 `{weight}`、`{family_sc}` 等占位符，解析为空文本时自动删除前导空格；每模板可携带**重命名模板**（空 = 应用模板时不重命名） |
| **翻译方案** | 字重/字宽/斜体标签的简繁日英跨语言定义，供下拉框、表格显示与占位符解析统一使用 |
| **设置** | 主题模式、预览文字与字号、开机自动启动、自动恢复选中、MPV 插件联动、关于与检查更新 |

### 字幕字体适配细节

- 从字幕的 **Style 行**（`[V4+ Styles]` / `[V4 Styles]` 的 Fontname 字段）与事件行的 **`{\fn字体名}`** 覆盖标签提取字体名，跨文件去重。
- 每个字体名一行，右侧下拉从**当前字体库**选择替换字体：与字体库完全匹配的自动预选，未匹配的留空（= 不替换）；下拉支持输入匹配（中文名或英文系统名，忽略大小写）。
- 确定后批量替换写回原文件，保留原编码（UTF-8 / UTF-16 BOM、GBK）与换行，`[Fonts]` 内嵌二进制节不受影响。

### 字体编辑细节

- **四语言编辑**：简（sc）/ 繁（tc）/ 日（jp）/ 英（en）语言开关，可单独显示/隐藏；每语言覆盖 name 表 20 个字段，勾选「保存」的语言才写入。
- **占位符解析**：重命名、模板应用、保存时支持 `{weight}`、`{weight_sc}`、`{width}`、`{italic}`、`{family_sc}`、`{subfamily_sc}`、`{preferred_family_sc}`、`{version_sc}`、`{name_sc}`、`{charset_sc}` 等动态变量；`xx` 可替换为 `sc`/`tc`/`jp`/`en`。
- **家族名原样保存**：家族名（nameID 1）按编辑值原样写回，不再按字重/字宽自动拼接。
- **子家族名隐式规则**：字重 700 → `Bold`，其余 → `Regular`，勾选保存的语言统一写入。
- **保存前解析**：未解析的 `{...}` 占位符在保存时自动展开为实际文本。
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
4. 用**翻译方案**页统一字重/字宽/斜体标签的简繁日英文案。
5. 在**设置**页配置主题、预览文字与字号、开机自启、自动恢复选中，以及 MPV 字幕字体联动。

---

## 下载与使用

从 Releases 或本地构建产物获取安装包 `FontTuner-<版本>-x64.zip`，解压后运行其中的安装程序即可。

安装过程**需要联网**：安装器会经 uv 自动下载 Python 环境并同步依赖，视网络情况等待几分钟。

> 打包安装后，数据文件 `data/templates.json`、`data/translations.json`、`data/fontmgr_cache.json` 与 `config.json` 存于 `%APPDATA%\FontTuner`（安装根不可写时回落），首次运行按默认值自动生成。

---

## 技术栈

- [PySide6](https://doc.qt.io/qtforpython/)（Qt 6 GUI）
- [PySide6-Fluent-Widgets](https://github.com/zhiyiYo/PySide6-Fluent-Widgets)（Fluent 设计组件）
- [fontTools](https://github.com/fonttools/fonttools)（字体解析 / TTC 打包解包）

---

## 支持

如果这个工具对你有所帮助，欢迎扫描下方二维码支持一下。捐赠无条件、无额外功能、无任何承诺，纯粹的支持与鼓励。

</br>

<!-- markdownlint-disable-next-line MD033 -->
<img src="res/img/bill.png" width="400" alt="收款码">

---

## 许可

[GPL-3.0](LICENSE) © 2026 拾字 FontTuner
