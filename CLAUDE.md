# 规则

- 禁止自动提交（git commit）和自动推送（git push），除非用户明确要求。

## 项目结构

- `src/` — 应用源码。`main.py` 为入口，`config.py` 全局配置，`core/` 业务逻辑，`ui/` 各页面（fontmgr 字体管理 / package 解包打包 / editor 字体编辑 / templates 信息模板 / translations 翻译方案 / help 帮助 / settings 设置）。
- `res/` — 资源目录。`res.qrc` 声明打包进资源的文件，经 `pyside6-rcc` 编译为 `src/res.py`（图标/启动图/帮助页 HTML）。修改 qrc 后需重新编译：
  ```bash
  uv run pyside6-rcc res/res.qrc -o src/res.py
  ```
  帮助页 HTML（`res/html/help.html`）由 `README.md` 经 pandoc 编译生成，改 README 后需再生成并重编译资源：
  ```bash
  build\make_help.bat      # 即 uv run build/make_help.py（pandoc --embed-resources）
  uv run pyside6-rcc res/res.qrc -o src/res.py
  ```
  帮助页样式不在 HTML 里，而是 `src/ui/help/frame.py` 运行时按明暗主题注入（`setDefaultStyleSheet`）。
- `build/` — 发布构建。`build_release.py` 一键发布（清理→uv 工具链→pyc 编译→资源→BatToExe 入口→Inno 安装器→zip→收尾），`build.bat` 一键入口，`setup.iss` Inno 安装脚本。
- `data/` 与 `config.json` — 运行时可写数据，开发态在仓库根，打包安装后自动回落 `%APPDATA%\FontTuner`。

## 运行与构建

- 开发运行：`uv run python -B src/main.py`
- 一键发布：`build.bat`（即 `uv run build/build_release.py`），产物在 `dist/`

## 版本号升级清单

升级版本号（如 `0.7.0` → `0.8.0`）时，需要同步修改以下文件：

| 文件                     | 内容                           |
| ------------------------ | ------------------------------ |
| `pyproject.toml`         | `version = "0.x.x"`            |
| `build/setup.iss`        | `#define MyAppVersion "0.x.x"`（`#ifndef` 守卫的默认值，发布脚本会以 pyproject 为准通过 `/D` 注入） |

> 发布脚本 `build/build_release.py` 通过正则读取 `pyproject.toml` 的 `version` 作为唯一权威版本号，因此升级时以它为准；`setup.iss` 的默认值仅保证脱离发布脚本单独编译时不缺版本号。
