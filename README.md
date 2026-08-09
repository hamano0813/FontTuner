# 拾字 FontTuner

[![Python](https://img.shields.io/badge/Python-%E2%89%A53.14-blue?logo=python&style=flat&labelColor=013243)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-6.7%2B-green?logo=qt&style=flat&labelColor=013243)](https://doc.qt.io/qtforpython-6/)
[![uv](https://img.shields.io/badge/uv-0.6%2B-261230?style=flat&labelColor=013243)](https://docs.astral.sh/uv/)
[![Inno Setup](https://img.shields.io/badge/Inno%20Setup-6.4%2B-blue?style=flat&labelColor=013243)](https://jrsoftware.org/isinfo.php)
[![Windows](https://img.shields.io/badge/Windows-10%2B-00A4EF?logo=windows&style=flat&labelColor=013243)](https://www.microsoft.com/windows)
[![GPLv3](https://img.shields.io/badge/License-GPLv3-red?logo=gnu&style=flat&labelColor=013243)](LICENSE)

> 字体元数据编辑 · TTC/OTC 解包打包 · 字体管理 —— 面向简体 / 繁体 / 日文 / 英文四语言的专业字体工具。

拾字 FontTuner 是一个基于 PySide6 + [PySide6-Fluent-Widgets](https://github.com/zhiyiYo/PySide6-Fluent-Widgets)（qfw）的 Windows 桌面应用。它围绕字体文件（`.ttf` / `.otf` / `.ttc` / `.otc`）的 **name 表元数据** 提供批量编辑能力，并附带 TTC/OTC 解包打包与字体注册管理。

---

## 功能一览

| 页面 | 说明 |
| --- | --- |
| **字体管理** | 树形浏览字体库文件夹，勾选即注册到 Windows（当前会话有效），系统已装字体灰显标记；目录级三态勾选、按名称/家族名筛选、底部多语言预览 |
| **解包打包** | `.ttc`/`.otc` 集合 → 拆成独立 `.ttf`/`.otf`；多个 `.ttf`/`.otf` → 合并成 `.ttc`/`.otc`。按字体内名称命名，重名自动加序号 |
| **字体编辑** | 批量编辑 name 表 20 个字段 × 简/繁/日/英四种语言：家族名、子家族名、唯一标识、全名、字体名、版权、厂商、许可等；字重/字宽/斜体直接编辑；临时名称/字符集占位列 |
| **信息模板** | 维护字体信息字段集（JSON 持久化），在「字体编辑」页一键应用到选中/全部字体；支持 `{weight}`、`{family_sc}` 等占位符，解析为空文本时自动删除前导空格 |
| **翻译方案** | 字重/字宽/斜体标签的简繁日英跨语言定义，供下拉框、表格显示与占位符解析统一使用 |
| **设置** | 主题模式/主题色、字体文件重命名模板、预览文字与字号、关于与版权 |

### 字体编辑细节

- **四语言编辑**：简（sc）/ 繁（tc）/ 日（jp）/ 英（en）语言开关，可单独显示/隐藏；每语言覆盖 name 表 20 个字段，勾选「保存」的语言才写入。
- **占位符解析**：重命名、模板应用、保存时支持 `{weight}`、`{weight_sc}`、`{width}`、`{italic}`、`{family_sc}`、`{subfamily_sc}`、`{preferred_family_sc}`、`{version_sc}`、`{name_sc}`、`{charset_sc}` 等动态变量；`xx` 可替换为 `sc`/`tc`/`jp`/`en`。
- **子家族名隐式规则**：字重 700 → `Bold`，其余 → `Regular`，勾选保存的语言统一写入。
- **保存前解析**：未解析的 `{...}` 占位符在保存时自动展开为实际文本。

---

## 快速上手

1. 在**字体管理**页勾选目标字体（或按目录三态勾选），即可注册到 Windows，系统已装字体自动灰显。
2. 用**解包打包**页拆分 `.ttc`/`.otc` 集合为独立字体，或在编辑后合并回集合。
3. 在**字体编辑**页批量修改 name 表元数据，配合**信息模板**一键套用预设字段集。
4. 用**翻译方案**页统一字重/字宽/斜体标签的简繁日英文案。
5. 在**设置**页配置主题、字体文件重命名模板与预览文字。

---

## 下载与使用

从 Releases 或本地构建产物获取安装包 `FontTuner-<版本>-x64.zip`，解压后运行其中的安装程序即可。

安装过程**需要联网**：安装器会经 uv 自动下载 Python 环境并同步依赖，视网络情况等待几分钟。

> 打包安装后，数据文件 `data/templates.json`、`data/translations.json` 与 `config.json` 存于 `%APPDATA%\FontTuner`（安装根不可写时回落），首次运行按默认值自动生成。

---

## 开发运行

环境要求：**Windows 10 / 11（64 位）**、**Python 3.14+**、[uv](https://docs.astral.sh/uv/)。

```bash
uv sync          # 安装依赖（fontTools、PySide6、qfluentwidgets）
uv run python -B src/main.py
```

> 开发态数据文件存放于仓库根；打包安装后自动改存 `%APPDATA%\FontTuner`。

---

## 发布构建

一键脚本仿 [srw_alpha](https://github.com/hamano0813/SRW_Alpha) 的发布方案，走 **Inno Setup 安装器 + 在线部署**（安装时经 uv 下载 Python 并同步依赖，安装包小、无需预装 Python）：

```bash
build.bat        # 即 uv run build/build_release.py
```

构建产物（`dist/`）：`FontTuner-<版本>-x64.zip`（内含 Inno Setup 安装器 `FontTuner-<版本>-x64.exe`）。

构建流程（8 步）：清理 dist → 准备 uv 工具链与依赖锁定 → 源码编译为 `.pyc` 到 `script/` → 复制许可/裁剪脚本 → BatToExe 生成 `FontTuner.exe` 入口 → ISCC 生成安装器 → 打包 zip → 清理中间产物。安装时 `setup.iss` 内置脚本：`uv python install` → `uv sync` → `trim_venv` 瘦身 → UPX 压缩，并提供下载镜像选择与卸载三选（普通 / 仅清 venv / 完全卸载）。

所需构建工具（需预先安装）：`uv`、[BatToExe](https://bat2exe.net/)（默认 `C:\Softwares\Bat2Exe\`）、[Inno Setup 6](https://jrsoftware.org/isinfo.php)（默认 `C:\Softwares\Inno Setup\`）、UPX（可选，PATH 内自动识别）。

---

## 技术栈

- [PySide6](https://doc.qt.io/qtforpython/)（Qt 6 GUI）
- [PySide6-Fluent-Widgets](https://github.com/zhiyiYo/PySide6-Fluent-Widgets)（Fluent 设计组件）
- [fontTools](https://github.com/fonttools/fonttools)（字体解析 / TTC 打包解包）

---

## 许可

[GPL-3.0](LICENSE) © 2026 拾字 FontTuner
