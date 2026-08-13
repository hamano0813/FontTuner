"""
拾字 FontTuner — .venv 裁剪脚本

在安装器 uv sync 完成后运行，删除安装环境下无用文件以缩减安装体积。
PySide6 模块取舍参考 qfluentwidgets 运行所需（QtCore/QtGui/QtWidgets/QtSvg/
QtSvgWidgets/QtXml 保留），其余按需删除。
"""
import glob
import os
import shutil
import sys


# ── PySide6 保留模块（qfw 运行时需要）──
KEEP_PYSIDE = frozenset({
    "QtCore", "QtGui", "QtWidgets",
    "QtSvg", "QtSvgWidgets", "QtXml",
    "QtNetwork",
    "QtDBus", "QtConcurrent",
    "QtOpenGL", "QtOpenGLWidgets",
    "QtPrintSupport",
})

# ── PySide6 删除模块 ──
REMOVE_PYSIDE = [
    # WebEngine —— 最大 (~200 MB)
    "QtWebEngineWidgets", "QtWebEngineCore", "QtWebEngineQuick",
    # QML 全家桶 (~100 MB)
    "QtQml", "QtQuick", "QtQuick3D", "QtQuickControls2",
    "QtQuickTest", "QtQuickWidgets",
    # 3D (~15 MB)
    "Qt3DAnimation", "Qt3DCore", "Qt3DExtras", "Qt3DInput",
    "Qt3DLogic", "Qt3DRender",
    # 图表 / 数据可视化 (~8 MB)
    "QtCharts", "QtDataVisualization", "QtGraphs", "QtGraphsWidgets",
    # 多媒体 (~6 MB)
    "QtMultimedia", "QtMultimediaWidgets", "QtSpatialAudio",
    # 硬件外设
    "QtBluetooth", "QtNfc", "QtPositioning", "QtLocation",
    "QtSensors", "QtSerialBus", "QtSerialPort",
    # 数据库
    "QtSql",
    # 网络扩展（保留 QtNetwork）
    "QtNetworkAuth", "QtWebSockets", "QtWebChannel",
    "QtHttpServer", "QtRemoteObjects",
    # 其他无用模块
    "QtHelp", "QtTextToSpeech", "QtUiTools", "QtScxml",
    "QtStateMachine", "QtDesigner", "QtCanvasPainter",
    "QtAxContainer", "QtTest", "QtPdf", "QtPdfWidgets",
    "QtWebView",
    # Qt Labs
    "QtLabsAnimation", "QtLabsFolderListModel", "QtLabsPlatform",
    "QtLabsQmlModels", "QtLabsSettings", "QtLabsSharedImage",
    "QtLabsStyleKit", "QtLabsSynchronizer", "QtLabsWavefrontMesh",
    # 其他 Qml 附属
    "QtLottie", "QtVirtualKeyboard", "QtShaderTools",
    "QtScxmlQml", "QtRemoteObjectsQml", "QtStateMachineQml",
    "QtChartsQml",
]

# ── PySide6 插件目录（仅被已删除模块使用）──
REMOVE_PLUGINS = [
    "assetimporters", "canbus", "designer",
    "geoservices", "multimedia", "position",
    "qmllint", "qmltooling",
    "renderers", "renderplugins", "sceneparsers",
    "scxmldatamodel", "sensors",
    "sqldrivers", "texttospeech", "webview",
]


def _rmdir(parent: str, name: str) -> int:
    """删除 parent/name 目录，返回释放的字节数"""
    path = os.path.join(parent, name)
    if not os.path.isdir(path):
        return 0
    total = 0
    for f in glob.glob(os.path.join(path, "**"), recursive=True):
        if os.path.isfile(f):
            total += os.path.getsize(f)
    shutil.rmtree(path, ignore_errors=True)
    return total


def trim_pyside6(pyside6_dir: str) -> int:
    """裁剪 PySide6 无用模块，返回删除的字节数"""
    if not os.path.isdir(pyside6_dir):
        return 0
    total = 0

    # .pyd + .pyi
    for module in REMOVE_PYSIDE:
        for ext in (".pyd", ".pyi"):
            path = os.path.join(pyside6_dir, module + ext)
            if os.path.isfile(path):
                total += os.path.getsize(path)
                os.remove(path)

    # Qt6*.dll（前缀匹配，捕获 Qt6QmlCompiler.dll 等附属 DLL）
    remove_prefixes = []
    for module in REMOVE_PYSIDE:
        if module.startswith("Qt"):
            remove_prefixes.append("Qt6" + module[2:])
    for fname in os.listdir(pyside6_dir):
        if not (fname.startswith("Qt6") and fname.endswith(".dll")):
            continue
        for prefix in remove_prefixes:
            if fname.startswith(prefix):
                path = os.path.join(pyside6_dir, fname)
                total += os.path.getsize(path)
                os.remove(path)
                break

    # 翻译文件：只留 en / zh_CN / ja_JP
    trans_dir = os.path.join(pyside6_dir, "translations")
    if os.path.isdir(trans_dir):
        keep = ("zh_CN.qm", "ja_JP.qm", "en.qm")
        for qm in glob.glob(os.path.join(trans_dir, "*.qm")):
            if any(qm.endswith(f"_{k}") for k in keep):
                continue
            total += os.path.getsize(qm)
            os.remove(qm)
        # 清理翻译目录下的子文件夹（如 qtwebengine_locales ~44MB）
        for name in os.listdir(trans_dir):
            sub = os.path.join(trans_dir, name)
            if os.path.isdir(sub):
                total += _rmdir(trans_dir, name)

    # 插件目录
    plugins_dir = os.path.join(pyside6_dir, "plugins")
    if os.path.isdir(plugins_dir):
        for name in REMOVE_PLUGINS:
            path = os.path.join(plugins_dir, name)
            if os.path.isdir(path):
                for f in glob.glob(os.path.join(path, "**"), recursive=True):
                    if os.path.isfile(f):
                        total += os.path.getsize(f)
                shutil.rmtree(path, ignore_errors=True)

    # Qt 命令行工具（assistant.exe / designer.exe / uic.exe / lupdate.exe 等）
    for fname in os.listdir(pyside6_dir):
        if fname.endswith(".exe"):
            path = os.path.join(pyside6_dir, fname)
            total += os.path.getsize(path)
            os.remove(path)

    # 独立无用文件（非 Qt6*.dll 命名规则，单独列出）
    for fname in ("opengl32sw.dll",
                  "avcodec-61.dll", "avformat-61.dll", "avutil-59.dll",
                  "swresample-5.dll", "swscale-8.dll"):
        path = os.path.join(pyside6_dir, fname)
        if os.path.isfile(path):
            total += os.path.getsize(path)
            os.remove(path)

    # QML 运行时文件（QtQuick / QtQml 等已删，qml/ 无用时占用 ~32MB）
    total += _rmdir(pyside6_dir, "qml")

    # WebEngine 运行时资源（~102MB: icudtl.dat / *.pak / v8 snapshot 等）
    total += _rmdir(pyside6_dir, "resources")

    # WebEngine 语言包
    total += _rmdir(pyside6_dir, "qtwebengine_locales")

    # C++ 开发头文件（运行时无用）
    total += _rmdir(pyside6_dir, "include")

    # 模块元类型 JSON（Designer/QML 工具链用，运行时不需要）
    total += _rmdir(pyside6_dir, "metatypes")

    return total


def trim_venv(venv_dir: str) -> None:
    """裁剪整个 .venv 中的无用文件"""
    if not os.path.isdir(venv_dir):
        print(f"[WARN] .venv not found: {venv_dir}")
        return

    total = 0
    site_pkg = os.path.join(venv_dir, "Lib", "site-packages")
    scripts_dir = os.path.join(venv_dir, "Scripts")

    # ── 1) PySide6 ──
    pyside6_dir = os.path.join(site_pkg, "PySide6")
    total += trim_pyside6(pyside6_dir)

    # ── 2) 所有 .pyi 文件（全 venv，类型桩仅供 IDE，运行时无用）──
    for root, _dirs, files in os.walk(venv_dir):
        for f in files:
            if f.endswith(".pyi"):
                path = os.path.join(root, f)
                total += os.path.getsize(path)
                os.remove(path)

    # ── 3) PyWin32.chm（离线文档）──
    chm = os.path.join(site_pkg, "PyWin32.chm")
    if os.path.isfile(chm):
        total += os.path.getsize(chm)
        os.remove(chm)

    # ── 3.5) PIL 的 AVIF 插件（本项目不用）──
    for rel in ("PIL/_avif.cp314-win_amd64.pyd", "PIL/_avif.pyi"):
        path = os.path.join(site_pkg, rel)
        if os.path.isfile(path):
            total += os.path.getsize(path)
            os.remove(path)

    # ── 4) setuptools + pip + scipy + numpy（纯构建/可选依赖，源码未引用）──
    # scipy/numpy 由 pyside6-fluent-widgets[full] 的 full extra 带入，仅服务
    # qfw 的 AcrylicLabel 磨砂与 DominantColor 取色，本程序未用到（壁纸随动是
    # Windows 原生 Mica/acrylic 背板，不走这两个包），故随 SRW Alpha 一并裁掉。
    for pkg in ("setuptools", "pip", "_distutils_hack", "scipy", "numpy",
                "scipy.libs", "numpy.libs"):
        path = os.path.join(site_pkg, pkg)
        if os.path.isdir(path):
            for f in glob.glob(os.path.join(path, "**"), recursive=True):
                if os.path.isfile(f):
                    total += os.path.getsize(f)
            shutil.rmtree(path, ignore_errors=True)
    # 清理 .pth 引用（_distutils_hack 已删，留着会报错）
    pth = os.path.join(site_pkg, "distutils-precedence.pth")
    if os.path.isfile(pth):
        total += os.path.getsize(pth)
        os.remove(pth)

    # ── 5) Scripts/pyside6-* （Qt 命令行工具，运行时不需要）──
    if os.path.isdir(scripts_dir):
        for fname in os.listdir(scripts_dir):
            if fname.startswith("pyside6-") and fname.endswith(".exe"):
                path = os.path.join(scripts_dir, fname)
                total += os.path.getsize(path)
                os.remove(path)

    # ── 6) site-packages 根级 mypyc 编译扩展（mypyc/ 目录删除后残留）──
    for fname in os.listdir(site_pkg):
        if fname.endswith("__mypyc.cp314-win_amd64.pyd"):
            path = os.path.join(site_pkg, fname)
            total += os.path.getsize(path)
            os.remove(path)
            break

    # ── 7) test 目录（各包自带的测试用例）──
    for root, dirs, _unused in os.walk(site_pkg):
        for d in dirs:
            if d in ("test", "tests"):
                path = os.path.join(root, d)
                for f in glob.glob(os.path.join(path, "**"), recursive=True):
                    if os.path.isfile(f):
                        total += os.path.getsize(f)
                shutil.rmtree(path, ignore_errors=True)

    mb = total / 1024 / 1024
    print(f"[INFO] venv trimmed: removed {mb:.1f} MB")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <.venv_directory>")
        sys.exit(1)
    trim_venv(sys.argv[1])
