"""qfw 兼容修正：InfoBar dropAni 无端值告警的继承式修复。

qfw 的 InfoBarManager.add 给叠放 InfoBar 创建的 dropAni（QPropertyAnimation on 'pos'）
只设了时长、未设 end value，真实窗口时序下被启动会报
`QPropertyAnimation::updateState (pos, InfoBar): starting an animation without end value`。

修复采用 qfw 官方机制的继承 + 覆写，而非 monkey-patch：子类覆写 add()，在创建 dropAni
后立即补上 start/end 端值（后续 _updateDropAni 会覆写为正确值，不影响行为），
再注册进 InfoBarManager.managers 注册表供 make() 使用。
"""

from __future__ import annotations

from qfluentwidgets.components.widgets.info_bar import (
    InfoBarManager,
    InfoBarPosition,
    TopInfoBarManager,
)


class FixedTopInfoBarManager(TopInfoBarManager):
    """修复 dropAni 无端值告警的 TOP 位置管理器子类。"""

    def add(self, infoBar) -> None:
        super().add(infoBar)
        drop = infoBar.property("dropAni")
        if drop is not None and drop.endValue() is None:
            drop.setStartValue(infoBar.pos())
            drop.setEndValue(self._pos(infoBar))


def apply() -> None:
    """在首个 InfoBar 出现前注册修复后的管理器（应用只用 TOP 位置）。"""
    InfoBarManager.managers[InfoBarPosition.TOP] = FixedTopInfoBarManager
