"""后台线程：解包 / 打包，避免大批次阻塞界面。"""

from PySide6.QtCore import QThread, Signal

from core import package


class UnpackWorker(QThread):
    progress = Signal(int, int)            # done, total
    finished_ok = Signal(object, object)   # outputs, errors

    def __init__(self, srcs: list[str], out_dir: str, parent=None):
        super().__init__(parent)
        self._srcs = srcs
        self._out_dir = out_dir

    def run(self):
        outputs, errors = package.unpack_fonts(
            self._srcs, self._out_dir, progress=self._emit_progress
        )
        self.finished_ok.emit(outputs, errors)

    def _emit_progress(self, done: int, total: int) -> None:
        self.progress.emit(done, total)


class PackWorker(QThread):
    progress = Signal(int, int)            # done, total
    finished_ok = Signal(object, object)   # out_path, errors

    def __init__(self, srcs: list[str], out_dir: str, out_name: str, fmt: str, parent=None):
        super().__init__(parent)
        self._srcs = srcs
        self._out_dir = out_dir
        self._out_name = out_name
        self._fmt = fmt

    def run(self):
        out_path, errors = package.pack_fonts(
            self._srcs, self._out_dir, self._out_name, self._fmt,
            progress=self._emit_progress,
        )
        self.finished_ok.emit(out_path, errors)

    def _emit_progress(self, done: int, total: int) -> None:
        self.progress.emit(done, total)
