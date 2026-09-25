"""可编程直流电源面板模型（QML <-> Python 桥接）。

一个仪器面板 = 1 个 QML 视图 + 1 个本类实例；
命令/查询通过控制器注入的回调下发到 HAL 仪器（真机或虚拟）。

SCPI（鼎阳 SPD 系列常见写法，待真机核对）见 autotest/hal/devices/power_siglent.py。
"""
from __future__ import annotations

from typing import Callable, Dict, Optional

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from ...bus.event_bus import bus

_POLL_MS = 1000


def _to_float(text: Optional[str]) -> Optional[float]:
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return None


class PowerPanel(QObject):
    """直流电源仪器面板。"""

    stateChanged = Signal()
    measurementsChanged = Signal()
    commandChanged = Signal()

    def __init__(self, instrument_id: str = "power1", channels: int = 3, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._iid = instrument_id
        self._channels = int(channels)
        self._channel = 1
        self._set: Dict[int, Dict[str, object]] = {
            ch: {"voltage": 5.0, "current": 1.0, "output": False}
            for ch in range(1, self._channels + 1)
        }
        self._measured: Dict[str, float] = {"voltage": 0.0, "current": 0.0}
        self._command_text = ""
        self._command_state = ""
        self._sink: Optional[Callable[[str], str]] = None
        self._query: Optional[Callable[[str], str]] = None

        self._timer = QTimer(self)
        self._timer.setInterval(_POLL_MS)
        self._timer.timeout.connect(self.refresh)

    # ---------- 生命周期 / 注入 ----------
    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def setCommandSink(self, sink: Callable[[str], str]) -> None:
        self._sink = sink

    def setQuerySink(self, query: Callable[[str], str]) -> None:
        self._query = query

    # ---------- 内部 ----------
    def _state(self) -> Dict[str, object]:
        return self._set[self._channel]

    def _apply(self, command: str, result: str = "") -> None:
        bus.publish("ui", "action", command.split()[0] if command else "", detail=command, source="sim")
        self._command_text = command
        state = "（未连接仪器）"
        if callable(self._sink):
            try:
                state = self._sink(command) or ""
            except Exception as exc:  # noqa: BLE001
                state = "下发异常: %s" % exc
        self._command_state = state
        self.commandChanged.emit()
        if result:
            bus.publish("glue", "slot", "power:" + command.split()[0], detail=command, result=result)

    # ---------- 属性 ----------
    @Property(int, notify=stateChanged)
    def channel(self) -> int:
        return self._channel

    @Property(bool, notify=stateChanged)
    def outputOn(self) -> bool:
        return bool(self._state()["output"])

    @Property(float, notify=stateChanged)
    def voltage(self) -> float:
        return float(self._state()["voltage"])

    @Property(float, notify=stateChanged)
    def current(self) -> float:
        return float(self._state()["current"])

    @Property(float, notify=measurementsChanged)
    def measuredVoltage(self) -> float:
        return float(self._measured["voltage"])

    @Property(float, notify=measurementsChanged)
    def measuredCurrent(self) -> float:
        return float(self._measured["current"])

    @Property(str, notify=commandChanged)
    def commandText(self) -> str:
        return self._command_text

    @Property(str, notify=commandChanged)
    def commandState(self) -> str:
        return self._command_state

    @Property(str, constant=True)
    def instrumentId(self) -> str:
        return self._iid

    # ---------- 槽：用户操作 ----------
    @Slot(int)
    def setChannel(self, channel: int) -> None:
        if 1 <= int(channel) <= self._channels:
            self._channel = int(channel)
            self.stateChanged.emit()
            self.refresh()

    @Slot(bool)
    def setOutput(self, on: bool) -> None:
        on = bool(on)
        self._state()["output"] = on
        self._apply(":CHANnel%d:OUTPut %s" % (self._channel, "ON" if on else "OFF"))
        self.stateChanged.emit()
        self.refresh()

    @Slot(float)
    def setVoltage(self, volts: float) -> None:
        self._state()["voltage"] = float(volts)
        self._apply(":CHANnel%d:VOLTage %.4f" % (self._channel, float(volts)))
        self.stateChanged.emit()
        self.refresh()

    @Slot(float)
    def setCurrent(self, amps: float) -> None:
        self._state()["current"] = float(amps)
        self._apply(":CHANnel%d:CURRent %.4f" % (self._channel, float(amps)))
        self.stateChanged.emit()
        self.refresh()

    @Slot()
    def refresh(self) -> None:
        """读取实测电压/电流（真机查询或虚拟电源仿真）。"""
        if not callable(self._query):
            return
        v = _to_float(self._query(":MEASure:VOLTage? CHANnel%d" % self._channel))
        i = _to_float(self._query(":MEASure:CURRent? CHANnel%d" % self._channel))
        self._measured["voltage"] = v if v is not None else 0.0
        self._measured["current"] = i if i is not None else 0.0
        self.measurementsChanged.emit()

    @Slot()
    def syncState(self) -> None:
        """从仪器回读输出状态（流程"停止回安全态"后调用，保证界面与实际一致）。"""
        if not callable(self._query):
            return
        changed = False
        for ch in range(1, self._channels + 1):
            resp = (self._query(":CHANnel%d:OUTPut?" % ch) or "").strip().upper()
            if resp:
                value = resp.startswith("ON")
                if bool(self._set[ch]["output"]) != value:
                    self._set[ch]["output"] = value
                    changed = True
        if changed:
            self.stateChanged.emit()
        self.refresh()

    @Slot()
    def saveSafe(self) -> None:
        """安全动作：关闭输出（供"停止流程自动回安全态"使用）。"""
        if bool(self._state()["output"]):
            self.setOutput(False)

