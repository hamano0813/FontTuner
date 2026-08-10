"""后台线程：扫描文件夹为字体树、批量安装/卸载用户字体，避免阻塞界面。"""

from PySide6.QtCore import QThread, Signal

from core import font_register, userfont


class ScanWorker(QThread):
    finished_ok = Signal(object, object)   # tree（根节点列表）, errors

    def __init__(self, roots: list[str], parent=None):
        super().__init__(parent)
        self._roots = roots

    def run(self):
        font_register.load_cache()  # 复用上次扫描的 mtime/size 缓存，未变化的字体不重读
        userfont.refresh_user_font_cache()  # 重建「已安装到当前用户」家族缓存
        errors: list[tuple[str, str]] = []
        tree: list[dict] = []
        for root in self._roots:
            node = font_register.scan_folder_tree(root, errors)
            if node is not None:
                tree.append(node)
        font_register.save_cache()
        self.finished_ok.emit(tree, errors)


class RegisterWorker(QThread):
    """批量注册/注销字体，避免大量 GDI 调用阻塞界面。"""

    progress = Signal(int, int)                          # done, total
    finished_ok = Signal(object, object, object)         # registered, unregistered, errors

    def __init__(self, to_register, to_unregister, parent=None):
        super().__init__(parent)
        self._to_register = list(to_register)
        self._to_unregister = list(to_unregister)

    def run(self):
        registered: list[str] = []
        unregistered: list[str] = []
        errors: list[tuple[str, str]] = []
        total = len(self._to_register) + len(self._to_unregister)
        done = 0
        for path in self._to_register:
            if font_register.register_font(path):
                registered.append(path)
            else:
                errors.append((path, "注册失败"))
            done += 1
            self.progress.emit(done, total)
        for path in self._to_unregister:
            if font_register.unregister_font(path):
                unregistered.append(path)
            else:
                errors.append((path, "注销失败（可能被占用）"))
            done += 1
            self.progress.emit(done, total)
        self.finished_ok.emit(registered, unregistered, errors)


class UserFontWorker(QThread):
    """批量安装/卸载到当前用户字体，避免复制+注册表阻塞界面。

    to_install 为 [(库路径, 家族名)]，to_uninstall 为 [(家族名, 库路径)]——
    库路径仅作界面回填 key，worker 不持有任何 Qt 控件引用。
    """

    progress = Signal(int, int)                     # done, total
    finished_ok = Signal(object)                    # list[dict] 每条安装/卸载结果

    def __init__(self, to_install, to_uninstall, parent=None):
        super().__init__(parent)
        self._to_install = list(to_install)
        self._to_uninstall = list(to_uninstall)

    def run(self):
        results: list[dict] = []
        total = len(self._to_install) + len(self._to_uninstall)
        done = 0
        for path, family in self._to_install:
            ok, error, installed = userfont.install_to_user(path, family)
            results.append({"kind": "install", "path": path, "family": family,
                            "ok": ok, "message": error, "installed_path": installed})
            done += 1
            self.progress.emit(done, total)
        for family, path in self._to_uninstall:
            ok, status, detail = userfont.uninstall_from_user(family)
            results.append({"kind": "uninstall", "path": path, "family": family,
                            "ok": ok, "status": status, "message": detail})
            done += 1
            self.progress.emit(done, total)
        self.finished_ok.emit(results)
