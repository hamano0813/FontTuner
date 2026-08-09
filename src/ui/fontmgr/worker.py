"""后台线程：扫描文件夹为字体树，避免大文件夹阻塞界面。"""

from PySide6.QtCore import QThread, Signal

from core import font_register


class ScanWorker(QThread):
    finished_ok = Signal(object, object)   # tree（根节点列表）, errors

    def __init__(self, roots: list[str], parent=None):
        super().__init__(parent)
        self._roots = roots

    def run(self):
        font_register.load_cache()  # 复用上次扫描的 mtime/size 缓存，未变化的字体不重读
        errors: list[tuple[str, str]] = []
        tree: list[dict] = []
        for root in self._roots:
            node = font_register.scan_folder_tree(root, errors)
            if node is not None:
                tree.append(node)
        font_register.save_cache()
        self.finished_ok.emit(tree, errors)
