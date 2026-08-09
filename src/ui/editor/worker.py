"""后台线程：加载字体 / 保存字体，避免大批次阻塞界面。"""

from PySide6.QtCore import QThread, Signal

from core import font_service


class LoadWorker(QThread):
    progress = Signal(int, int)          # done, total
    finished_ok = Signal(object, object)  # entries, errors

    def __init__(self, paths: list[str], parent=None):
        super().__init__(parent)
        self._paths = paths

    def run(self):
        entries, errors = font_service.load_entries(
            self._paths, progress=self._emit_progress
        )
        self.finished_ok.emit(entries, errors)

    def _emit_progress(self, done: int, total: int) -> None:
        self.progress.emit(done, total)


class SaveWorker(QThread):
    progress = Signal(int, int)          # done, total
    finished_ok = Signal(object)         # errors

    def __init__(self, entries: list, parent=None, release_font=None):
        super().__init__(parent)
        self._entries = entries
        self._release_font = release_font

    def run(self):
        errors = font_service.save_entries(
            self._entries, progress=self._emit_progress,
            release_font=self._release_font,
        )
        self.finished_ok.emit(errors)

    def _emit_progress(self, done: int, total: int) -> None:
        self.progress.emit(done, total)
