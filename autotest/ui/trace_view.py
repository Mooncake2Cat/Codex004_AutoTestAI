"""分层事件总线 → QML 桥接（阶段 1 的临时"分层跟踪"视图）。

事件总线是纯 Python 的；本模块把它接到 Qt：
  - 订阅总线事件，通过 Qt Signal 投递到界面线程（后台线程发布也安全）；
  - 提供统计与清空接口给 QML。
阶段 2 会用正式的"架构台窗口"替换本视图，接口保持不变。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Property, QObject, Signal, Slot

from ..bus.event_bus import EventBus, get_bus


class TraceBridge(QObject):
    """把事件总线的事件转发给 QML。"""

    eventLogged = Signal("QVariantMap")
    statsChanged = Signal("QVariantMap")

    def __init__(self, event_bus: Optional[EventBus] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._bus = event_bus or get_bus()
        self._unsubscribe = self._bus.subscribe(self._on_event)

    # ---------- 总线订阅 ----------
    def _on_event(self, payload: Dict[str, Any]) -> None:
        # 可能来自后台线程；Qt 自动使用排队连接投递到界面线程
        self.eventLogged.emit(payload)

    # ---------- 供 QML 调用 ----------
    @Slot(result="QVariantMap")
    def stats(self) -> Dict[str, Any]:
        return self._bus.stats()

    @Slot(result="QVariantList")
    def snapshot(self) -> List[Dict[str, Any]]:
        return self._bus.snapshot()

    @Slot()
    def clear(self) -> None:
        self._bus.clear()
        self.statsChanged.emit(self._bus.stats())

    @Slot()
    def refreshStats(self) -> None:
        self.statsChanged.emit(self._bus.stats())

    @Property(int, constant=True)
    def capacity(self) -> int:
        return self._bus.stats().get("capacity", 500)
