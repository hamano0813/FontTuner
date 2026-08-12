"""拾字 FontTuner 一键发布脚本

采用编号步骤编排，版本号从 pyproject.toml 读取、
dist/ 最终只保留发布产物。分发模型为「源码编译为 .pyc + uv 工具链」，由 Inno Setup
安装器在安装时在线装 Python 与依赖（安装包小，安装需联网）。

产物为两个 zip：
  - FontTuner-{version}-x64.zip   安装程序（内含 update.exe 与 version）
  - v{version}.zip                升级包（script/*.pyc + FontTuner.exe + version，
                                   由 update.exe 或设置页「检查更新」应用）

用法:
    cd 项目根目录
    uv run build/build_release.py

依赖（构建工具需提前安装）:
    - Python 3.14+ / uv
    - BatToExeConverter (C:\\Softwares\\Bat2Exe\\，把 main.bat 打包成 FontTuner.exe)
    - Inno Setup 6 (C:\\Softwares\\Inno Setup\\，生成安装程序)
    - UPX（可选，装进 .venv 时压缩 .pyd）
"""

import glob
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = PROJECT_ROOT / "build"
DIST_DIR = PROJECT_ROOT / "dist"
SCRIPT_DIR = DIST_DIR / "script"

# ======================== 项目配置 ========================
APP_NAME = "FontTuner"          # exe / 目录名（ASCII，避免路径问题）
APP_TITLE = "拾字 FontTuner"     # 安装器/产品名
APP_SHORT = "FontTuner"
APP_DESC = "字体元数据编辑 / 解包打包 / 字体管理工具"
COPYRIGHT = "Copyright © 2026 Hamano0813"

# 入口与顶层文件（编译为 script/ 下的 .pyc）
ENTRY_BAT = "main.bat"           # build/main.bat → 安装根执行入口
TOP_FILES = ["main.py", "config.py", "res.py"]
SRC_PACKAGES = ["core", "ui"]    # 编译为 script/<pkg>/*.pyc

# 外部工具（缺失则对应步骤跳过并警告）
BAT2EXE = r"C:\Softwares\Bat2Exe\BatToExeConverter.exe"
ISCC = r"C:\Softwares\Inno Setup\ISCC.exe"

# ======================== 日志与工具 ========================

def banner(title: str) -> None:
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def step(num: str, title: str) -> None:
    print(f"\n\033[1m[STEP {num}] {title}\033[0m")


def log(msg: str) -> None:
    print(f"  [INFO] {msg}")


def ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def error(msg: str) -> None:
    print(f"  [ERROR] {msg}")
    sys.exit(1)


def run(cmd, cwd=None, check=True) -> subprocess.CompletedProcess:
    """执行命令并捕获输出"""
    result = subprocess.run(
        cmd, cwd=cwd,
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if result.returncode != 0 and check:
        print(f"  [ERROR] Command failed: {' '.join(str(c) for c in cmd)}")
        if result.stdout:
            for line in result.stdout.splitlines():
                print(f"    | {line}")
        if result.stderr:
            for line in result.stderr.splitlines():
                print(f"    | {line}")
        sys.exit(1)
    return result


def find_version() -> str:
    """从 pyproject.toml 读取版本号"""
    pyproject = PROJECT_ROOT / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        error("pyproject.toml 中未找到 version 字段")
    return m.group(1)


# ======================== STEP 1/9: 清理 ========================

def step_clean():
    step("1/9", "清理构建目录")
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)
    SCRIPT_DIR.mkdir(parents=True)
    ok("dist/ 已清理")


# ======================== STEP 2/9: UV 工具链 ========================

def step_uv():
    """升级 uv、锁定依赖、复制 uv 工具链到 dist（供安装器在线部署）"""
    step("2/9", "准备 UV 工具链与依赖锁定")

    run(["uv", "self", "update"], check=False)

    # 只升级直接依赖（fonttools / pyside6-fluent-widgets），不动无关传递依赖——
    # 全量 --upgrade 会连带把 macOS 才用的 pyobjc 12.2.1 升到 12.2.2，每次构建都
    # 弄脏提交在仓库里的 uv.lock（Windows 上根本用不到 pyobjc）。只升级直接依赖
    # 已足够让安装器拿到最新版项目依赖，锁文件保持干净可复现。
    run(["uv", "lock", "--upgrade-package", "fonttools",
         "--upgrade-package", "pyside6-fluent-widgets"], check=False)

    # 安装器在部署阶段用 uv.exe 在线装 Python 与依赖（uv.toml 提供镜像）
    uv_exe = Path(os.environ["USERPROFILE"]) / ".local" / "bin" / "uv.exe"
    if uv_exe.exists():
        shutil.copy2(uv_exe, DIST_DIR / "uv.exe")
        ok("uv.exe")

    uv_toml = BUILD_DIR / "uv.toml"
    if uv_toml.exists():
        shutil.copy2(uv_toml, DIST_DIR / "uv.toml")
        ok("uv.toml")
        # uv self update / 重装 uv 可能清掉全局 uv.toml（镜像配置），缺失时从 build/
        # 副本恢复，保证构建与日常开发仍走 aliyun/python 镜像；已有则不动（尊重用户改动）
        global_uv_toml = Path(os.environ.get("APPDATA", "")) / "uv" / "uv.toml"
        if not global_uv_toml.exists():
            global_uv_toml.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(uv_toml, global_uv_toml)
            log(f"已从 build/uv.toml 恢复全局 uv 配置: {global_uv_toml}")

    for f in (".python-version", "pyproject.toml", "uv.lock"):
        src = PROJECT_ROOT / f
        if src.exists():
            shutil.copy2(src, DIST_DIR / f)
            ok(f)


# ======================== STEP 3/9: Python 编译为 .pyc ========================

def step_python_compile():
    """把 src/ 下源码编译为 .pyc 放到 dist/script/（含包结构）"""
    step("3/9", "编译 Python 源码")
    import py_compile

    src_root = PROJECT_ROOT / "src"

    for f in TOP_FILES:
        py_file = src_root / f
        if py_file.exists():
            pyc_target = SCRIPT_DIR / f
            pyc_target = pyc_target.with_suffix(".pyc")
            py_compile.compile(str(py_file), cfile=str(pyc_target), doraise=True)
            ok(f"{f} → .pyc")

    for pkg in SRC_PACKAGES:
        pkg_dir = src_root / pkg
        if not pkg_dir.exists():
            warn(f"跳过不存在的包: {pkg}")
            continue
        for py_file in sorted(pkg_dir.rglob("*.py")):
            if "build" in py_file.parts or "__pycache__" in py_file.parts:
                continue
            rel = py_file.relative_to(src_root)
            pyc_target = SCRIPT_DIR / rel.with_suffix(".pyc")
            pyc_target.parent.mkdir(parents=True, exist_ok=True)
            try:
                py_compile.compile(str(py_file), cfile=str(pyc_target), doraise=True)
            except py_compile.PyCompileError as e:
                error(f"编译失败: {rel} — {e}")

    # 清理 __pycache__（py_compile 默认会写）
    for cache in SCRIPT_DIR.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)

    log(f"Python 编译完成 → {SCRIPT_DIR}")


# ======================== STEP 4/9: 复制额外资源 ========================

def step_assets():
    step("4/9", "复制额外资源")

    # version 文件：以 pyproject.toml 为唯一权威，构建时同步仓库根（开发态显示/比对用）
    # 并生成 dist/version（升级包/安装器共用，装入 {app} 供版本比对）
    version = find_version()
    PROJECT_ROOT.joinpath("version").write_text(version, encoding="utf-8")
    DIST_DIR.joinpath("version").write_text(version, encoding="utf-8")
    ok("version")

    for asset in ("LICENSE", "README.md"):
        src = PROJECT_ROOT / asset
        if src.exists():
            shutil.copy2(src, DIST_DIR / asset)
            ok(asset)

    for f in ("uninstall_helper.ps1", "trim_venv.py"):
        src = BUILD_DIR / f
        if src.exists():
            shutil.copy2(src, DIST_DIR / f)
            ok(f)

    upx = shutil.which("upx.exe")
    if upx:
        shutil.copy2(upx, DIST_DIR / "upx.exe")
        # 配套的 man 文件（setup.iss 会引用）
        upx_dir = Path(upx).parent
        upx_man = upx_dir / "upx.1"
        if upx_man.exists():
            shutil.copy2(upx_man, DIST_DIR / "upx.1")
        ok("upx.exe (自 PATH)")
    else:
        warn("UPX 未找到，跳过压缩工具复制（安装时 UPX 步骤将被跳过）")


# ======================== STEP 5/9: 生成 EXE 入口 ========================

def step_entry_point():
    """把 main.bat 编译为 FontTuner.exe（BatToExe）"""
    step("5/9", "生成程序入口")

    if not os.path.exists(BAT2EXE):
        warn(f"BatToExeConverter 未找到: {BAT2EXE}，跳过 exe 生成")
        return

    version = find_version()
    icon = PROJECT_ROOT / "res" / "icon.ico"

    shutil.copy2(BUILD_DIR / ENTRY_BAT, DIST_DIR / ENTRY_BAT)

    # 注意：icon 路径必须用正斜杠，BatToExe 对反斜杠的 /icon 参数会报资源错误
    icon_arg = str(icon).replace("\\", "/")

    cmd = [
        BAT2EXE,
        "/bat", str(BUILD_DIR / ENTRY_BAT),
        "/exe", str(DIST_DIR / f"{APP_NAME}.exe"),
        "/invisible",
        "/overwrite",
        "/productname", APP_TITLE,
        "/description", APP_DESC,
        "/internalname", APP_SHORT,
        "/fileversion", f"{version}.0",
        "/productversion", f"{version}.0",
        "/copyright", COPYRIGHT,
    ]
    if icon.exists():
        cmd.extend(["/icon", icon_arg])

    # BatToExe 偶发「Couldn't add resources」（疑被安全软件短暂锁文件），重试至成功
    result = None
    for attempt in range(5):
        result = run(cmd, check=False)
        if result.returncode == 0 and (DIST_DIR / f"{APP_NAME}.exe").exists():
            break
        log(f"BatToExe 第 {attempt + 1} 次失败，重试…")
        time.sleep(1)
    else:
        error(f"BatToExe 连续失败：{BAT2EXE}")
    if not (DIST_DIR / f"{APP_NAME}.exe").exists():
        error("入口 exe 未生成")
    ok(f"{APP_NAME}.exe (v{version})")


# ======================== STEP 6/9: 编译更新程序 ========================

def step_update_binary():
    """编译 update.exe (Go)：供设置页「检查更新」与手动双击应用升级包"""
    step("6/9", "编译更新程序")

    go_exe = shutil.which("go")
    if not go_exe:
        warn("Go 未找到，跳过 update.exe 编译")
        return

    version = find_version()
    src_dir = BUILD_DIR / "update"
    if not src_dir.exists():
        warn(f"update 源码目录不存在: {src_dir}，跳过 update.exe 编译")
        return
    out_exe = DIST_DIR / "update.exe"

    cmd = [
        go_exe, "build",
        "-C", str(src_dir),
        "-ldflags", f"-s -w -X main.version={version}",
        "-o", str(out_exe),
        ".",
    ]
    run(cmd)
    ok(f"update.exe (v{version})")


# ======================== STEP 7/9: 生成安装程序 ========================

def step_installer():
    """调用 ISCC 生成 Inno Setup 安装程序"""
    step("7/9", "生成安装程序")

    if not os.path.exists(ISCC):
        warn(f"ISCC 未找到: {ISCC}，跳过安装程序生成")
        return

    version = find_version()
    iss_src = BUILD_DIR / "setup.iss"
    if iss_src.exists():
        shutil.copy2(iss_src, DIST_DIR / "setup.iss")

    icon = PROJECT_ROOT / "res" / "icon.ico"
    cmd = [ISCC, "/Qp",
           f"/DMyAppVersion={version}",
           f"/DMyAppIcon={icon}",
           str(DIST_DIR / "setup.iss")]
    run(cmd, cwd=str(DIST_DIR))

    exe_name = f"{APP_NAME}-{version}-x64.exe"
    if not (DIST_DIR / exe_name).exists():
        error(f"安装程序未生成: {exe_name}")
    ok(exe_name)


# ======================== STEP 8/9: 生成 ZIP 压缩包 ========================

def step_zip():
    """把安装程序打成 zip（GitHub Release 分发用）"""
    step("8/9", "生成 ZIP 压缩包")

    version = find_version()
    exe_name = f"{APP_NAME}-{version}-x64.exe"
    zip_name = f"{APP_NAME}-{version}-x64.zip"

    exe_path = DIST_DIR / exe_name
    if not exe_path.exists():
        warn(f"安装程序未找到: {exe_name}")
        return

    with zipfile.ZipFile(DIST_DIR / zip_name, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(exe_path, arcname=exe_name)
    ok(zip_name)


# ======================== STEP 9/9: 生成更新包 ========================

def step_update_package():
    """把 script/ 打包为 GitHub Release 更新包 (v{version}.zip)"""
    step("9/9", "生成更新包 (script zip)")

    if not SCRIPT_DIR.exists():
        warn(f"script 目录不存在，跳过: {SCRIPT_DIR}")
        return

    version = find_version()
    zip_name = f"v{version}.zip"
    zip_path = DIST_DIR / zip_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(SCRIPT_DIR.rglob("*")):
            if file_path.is_file():
                arcname = f"script/{file_path.relative_to(SCRIPT_DIR).as_posix()}"
                zf.write(file_path, arcname=arcname)
        # 附带启动器（主程序入口，更新版本时一起下发）
        exe_path = DIST_DIR / f"{APP_NAME}.exe"
        if exe_path.exists():
            zf.write(exe_path, arcname=f"{APP_NAME}.exe")

        # 附带 version 文件到 zip 根目录，覆盖旧版本号
        ver_file = DIST_DIR / "version"
        if ver_file.exists():
            zf.write(ver_file, arcname="version")

    file_count = sum(1 for _ in SCRIPT_DIR.rglob("*") if _.is_file())
    ok(f"{zip_name} ({file_count} 文件 + exe + version)")


# ======================== 收尾：清理 dist ========================

def step_finalize():
    """清理 dist，仅保留安装包 zip 与更新包 zip"""
    step("收尾", "清理中间产物，仅保留发布产物")

    version = find_version()
    keep = {f"{APP_NAME}-{version}-x64.zip", f"v{version}.zip"}

    removed_files = 0
    removed_dirs = 0
    for entry in list(DIST_DIR.iterdir()):
        if entry.name in keep:
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
            removed_dirs += 1
        else:
            entry.unlink()
            removed_files += 1

    if removed_files or removed_dirs:
        log(f"清理了 {removed_files} 个文件 / {removed_dirs} 个目录")
    for name in sorted(keep):
        ok(f"✓ {name}")


# ======================== 主流程 ========================

def main() -> int:
    # 强制 UTF-8 输出，避免 GBK 控制台打印 © 等字符时 UnicodeEncodeError
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    version = find_version()

    print()
    banner(f"{APP_TITLE} v{version} — 发布包构建")
    print(f"  项目根目录: {PROJECT_ROOT}")

    step_clean()
    step_uv()
    step_python_compile()
    step_assets()
    step_entry_point()
    step_update_binary()
    step_installer()
    step_zip()
    step_update_package()
    step_finalize()

    print()
    banner("构建完成！")
    ok(f"dist/ 剩余: {APP_NAME}-{version}-x64.zip + v{version}.zip")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
