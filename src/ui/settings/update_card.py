"""设置页「版权信息」卡片（含检查更新按钮）：显示版权与当前版本，点击检查更新 →
查 GitHub 最新 → 下载 v{version}.zip → 调 update.exe 重启。

参照 srw_alpha 的 UpdatePushSettingCard（标题 About、内容版权、按钮 Update），
但改为硬编码中文（FontTuner 设置页无 tr() 机制）。
"""

import json
import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import QDialog, QHBoxLayout
from qfluentwidgets import (
    FluentIcon as FIF,
    InfoBar,
    MessageBox,
    PrimaryPushSettingCard,
    ProgressRing,
    isDarkTheme,
)

from core.updater import install_dir, launch_update, read_version

_REPO = "hamano0813/FontTuner"


def _parse_ver(s: str) -> tuple:
    try:
        return tuple(int(x) for x in s.split("."))
    except (ValueError, TypeError):
        return ()


class UpdateCard(PrimaryPushSettingCard):
    """自包含的检查更新卡片 — 检查版本 → 下载 → 调 update.exe 重启"""

    def __init__(self, parent=None):
        ver = read_version()
        content = "© 2026 拾字 FontTuner · 保留所有权利"
        if ver:
            content += f" · 当前版本 v{ver}"
        super().__init__("检查更新", FIF.SYNC, "版权信息", content, parent)
        self.clicked.connect(self._start_check)
        self.button.setFixedWidth(120)

        # 内部状态
        self._current_ver: str = ""
        self._zip_asset: dict | None = None
        self._progress_dlg: QDialog | None = None
        self._progress_ring: ProgressRing | None = None
        self._nam: QNetworkAccessManager | None = None

    # ---------- 入口 ----------

    def _start_check(self):
        """按钮点击：读取本地版本后查询 GitHub"""
        current = read_version()
        if not current:
            InfoBar.error(title="检查更新", content="未找到版本文件，请重新安装程序。",
                          parent=self.window())
            return

        self._current_ver = current
        self._zip_asset = None
        self.button.setText("检查中...")
        self.button.setEnabled(False)

        url = QUrl(f"https://api.github.com/repos/{_REPO}/releases/latest")
        req = QNetworkRequest(url)
        req.setRawHeader(b"Accept", b"application/json")
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            req.setRawHeader(b"Authorization", f"Bearer {token}".encode())
        req.setTransferTimeout(10_000)

        self._nam = QNetworkAccessManager(self)
        self._nam.finished.connect(self._on_check_done)
        self._nam.get(req)

    # ---------- 版本检查回调 ----------

    def _on_check_done(self, reply):
        """GitHub API 返回后比对版本"""
        self.button.setText("检查更新")
        self.button.setEnabled(True)

        err = reply.error()
        if err != type(err).NoError:
            InfoBar.error(title="检查更新",
                          content="无法连接 GitHub，请检查网络或前往 Releases 页手动下载：\n"
                                  "https://github.com/hamano0813/FontTuner/releases/latest",
                          parent=self.window(), duration=6000)
            reply.deleteLater()
            return

        try:
            data = json.loads(reply.readAll().data().decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            InfoBar.warning(title="检查更新", content="无法解析更新信息。", parent=self.window())
            reply.deleteLater()
            return
        finally:
            reply.deleteLater()

        latest = data.get("tag_name", "").lstrip("v")
        cur_v = _parse_ver(self._current_ver)
        lat_v = _parse_ver(latest)

        if not cur_v or not lat_v:
            InfoBar.warning(title="检查更新", content="版本号格式无效。", parent=self.window())
            return

        if lat_v > cur_v:
            assets = data.get("assets", [])
            # 优先取 v0.x.x.zip（升级包），没有才取其他 zip
            self._zip_asset = next(
                (a for a in assets if a.get("name", "").startswith("v") and a["name"].endswith(".zip")),
                next((a for a in assets if a.get("name", "").endswith(".zip")), None),
            )
            if not self._zip_asset:
                InfoBar.warning(title="检查更新", content="发布页中未找到升级包。", parent=self.window())
                return
            box = MessageBox("发现新版本",
                             f"发现新版本 v{latest}，当前版本 v{self._current_ver}。\n\n立即更新？",
                             self.window())
            box.yesButton.setText("立即更新")
            box.cancelButton.setText("稍后")
            if box.exec():
                self._start_download()
        elif lat_v == cur_v:
            InfoBar.success(title="检查更新",
                            content=f"当前已是最新版本 v{self._current_ver}。",
                            parent=self.window(), duration=3000)
        else:
            InfoBar.info(title="检查更新",
                         content=f"当前版本 v{self._current_ver} 比最新发布版更新，可能是开发版。",
                         parent=self.window(), duration=4000)

    # ---------- 下载 ----------

    def _start_download(self):
        """弹出进度环并开始下载"""
        self.button.setText("更新中...")
        self.button.setEnabled(False)

        # 进度环弹窗（无边框，跟随主题）
        self._progress_dlg = QDialog(self.window(), f=Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self._progress_dlg.setFixedSize(160, 140)
        if isDarkTheme():
            self._progress_dlg.setStyleSheet("QDialog{background:#292929;}")
        else:
            self._progress_dlg.setStyleSheet("QDialog{background:white;}")

        self._progress_ring = ProgressRing(self._progress_dlg)
        self._progress_ring.setRange(0, 100)
        self._progress_ring.setValue(0)
        self._progress_ring.setTextVisible(True)
        self._progress_ring.setFormat("%v%")
        self._progress_ring.setStrokeWidth(6)
        self._progress_ring.setFixedSize(100, 100)

        layout = QHBoxLayout(self._progress_dlg)
        layout.addWidget(self._progress_ring)
        self._progress_dlg.setLayout(layout)
        self._progress_dlg.show()

        # 开始下载
        url = QUrl(self._zip_asset["browser_download_url"])
        req = QNetworkRequest(url)
        req.setTransferTimeout(120_000)

        self._dl_nam = QNetworkAccessManager(self)
        self._dl_reply = self._dl_nam.get(req)
        self._dl_reply.downloadProgress.connect(self._on_dl_progress)
        self._dl_nam.finished.connect(self._on_dl_done)

    def _on_dl_progress(self, received: int, total: int):
        if total > 0 and self._progress_ring:
            self._progress_ring.setValue(int(received * 100 / total))

    def _on_dl_done(self, reply):
        """下载完成：保存到安装目录 → 询问是否重启"""
        if self._progress_dlg:
            self._progress_dlg.close()

        err = reply.error()
        if err != type(err).NoError:
            self._show_error("下载失败，请检查网络后重试。")
            reply.deleteLater()
            return

        data = reply.readAll().data()
        filename = self._zip_asset["name"] if self._zip_asset else "update.zip"
        reply.deleteLater()

        base = install_dir()
        if not base:
            self._show_error("未找到安装目录（开发模式不支持自动更新）。")
            return

        dst = os.path.join(str(base), filename)
        try:
            with open(dst, "wb") as f:
                f.write(data)
        except OSError as e:
            self._show_error(str(e))
            return

        # 询问是否重启
        box = MessageBox("检查更新", "更新包已下载并安装，立即重启以应用更新？", self.window())
        box.yesButton.setText("立即重启")
        box.cancelButton.setText("稍后")
        if box.exec():
            launch_update()
        else:
            self.button.setText("检查更新")
            self.button.setEnabled(True)

    # ---------- 辅助 ----------

    def _show_error(self, msg: str):
        self.button.setText("检查更新")
        self.button.setEnabled(True)
        InfoBar.error(title="检查更新", content=msg, parent=self.window(), duration=6000)
