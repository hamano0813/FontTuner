"""进程级单实例守护：QLockFile 防止多开 + QLocalServer 唤醒已运行实例。

主实例持有锁文件并监听本地命名管道；第二个实例拿不到锁时连上该管道发送
唤醒标记后立即退出。主实例收到连接后把主窗口带到前台——程序可隐藏到托盘，
双开会自动唤出已有窗口，而不是静默无反应。

锁文件放系统临时目录，进程崩溃后按 PID 自动清理残留（setStaleLockTime(0)）；
命名管道在进程退出时由系统回收，无需额外清理。
"""

from __future__ import annotations

import os

from PySide6.QtCore import QLockFile, QStandardPaths
from PySide6.QtNetwork import QLocalServer, QLocalSocket

_APP_NAME = "FontTuner"
_WAKE_MARK = b"activate"


class SingleInstance:
    """acquire() 返回 True 表示本实例是主实例。

    主实例把 server.newConnection 连接到唤醒处理；次实例调用 request_activate()
    请求主实例把窗口带到前台后退出。
    """

    def __init__(self, app_name: str = _APP_NAME):
        temp = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation)
        self._lock = QLockFile(os.path.join(temp, f"{app_name}.lock"))
        self._lock.setStaleLockTime(0)  # 严格按 PID 判断残留，进程崩溃后立即让位
        self._pipe_name = app_name + "_Wake"
        self._server: QLocalServer | None = None

    def acquire(self) -> bool:
        """尝试成为主实例。返回 False 表示已有实例在运行。"""
        if not self._lock.tryLock(0):
            return False
        self._server = QLocalServer()
        self._server.removeServer(self._pipe_name)  # 清理可能的残留管道名
        self._server.listen(self._pipe_name)
        return True

    def release(self) -> None:
        """退出时释放锁与管道（进程退出时系统也会回收，此处为显式清理）。"""
        if self._server is not None:
            self._server.close()
            self._server = None
        if self._lock.isLocked():
            self._lock.unlock()

    @property
    def server(self) -> QLocalServer | None:
        return self._server

    def request_activate(self) -> None:
        """次实例：请求主实例把窗口带到前台（主实例不在则静默忽略）。"""
        sock = QLocalSocket()
        sock.connectToServer(self._pipe_name, QLocalSocket.OpenModeFlag.WriteOnly)
        if sock.waitForConnected(300):
            sock.write(_WAKE_MARK)
            sock.flush()
        sock.disconnectFromServer()
