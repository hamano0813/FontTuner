from PySide6.QtCore import QObject, Signal


class _AppSignals(QObject):
    """应用级全局信号单例，供各模块 import 后直接 emit/connect。"""

    project_edited = Signal()   # 任意数据被修改 → 置脏标记
    project_saved = Signal()    # 保存完成 → 清脏标记
    fonts_loaded = Signal()     # 字体列表加载完成


app_signals = _AppSignals()
