"""虚拟电源（Siglent SPD3303X-E 仿真）。

无真机时用于软件框架调试：以文本方式响应与真机驱动相同的 SCPI 命令，
内部维护每通道的设定值 / 输出状态 / 实测值。

仿真行为：
  - 输出 ON  → 实测电压 = 设定电压，实测电流 = 设定电流 × 0.5（模拟约半载）
  - 输出 OFF → 实测电压、电流 ≈ 0
"""
from __future__ import annotations

import re
from typing import Dict, Optional

from ...bus.event_bus import bus
from ..instrument import Instrument

_IDN = "Siglent Technologies,SPD3303X-E,MOCK-SPD-000001,1.0.0"

_RE_VOLT_SET = re.compile(r"^:CHANnel(\d+):VOLTage\s+([-\d.]+)$", re.IGNORECASE)
_RE_CURR_SET = re.compile(r"^:CHANnel(\d+):CURRent\s+([-\d.]+)$", re.IGNORECASE)
_RE_OUT_SET = re.compile(r"^:CHANnel(\d+):OUTPut\s+(ON|OFF|1|0)$", re.IGNORECASE)
_RE_VOLT_GET = re.compile(r"^:CHANnel(\d+):VOLTage\?$", re.IGNORECASE)
_RE_CURR_GET = re.compile(r"^:CHANnel(\d+):CURRent\?$", re.IGNORECASE)
_RE_OUT_GET = re.compile(r"^:CHANnel(\d+):OUTPut\?$", re.IGNORECASE)
_RE_MEAS_VOLT = re.compile(r"^:MEASure:VOLTage\?\s+CHANnel(\d+)$", re.IGNORECASE)
_RE_MEAS_CURR = re.compile(r"^:MEASure:CURRent\?\s+CHANnel(\d+)$", re.IGNORECASE)


class MockPowerSupply(Instrument):
    """虚拟可编程直流电源（多通道）。"""

    def __init__(self, instrument_id: str = "power-1", channels: int = 3):
        self._instrument_id = instrument_id
        self.channels = int(channels)
        self._state: Dict[int, Dict[str, object]] = {
            ch: {"voltage": 5.0, "current": 1.0, "output": False}
            for ch in range(1, self.channels + 1)
        }

    # ---------- 生命周期 ----------
    def initialize(self) -> None:
        return None

    def close(self) -> None:
        return None

    # ---------- 写入（设定） ----------
    def write(self, command: str) -> None:
        key = command.strip()
        with bus.span("hal", "command", "write", detail=key, source="sim"):
            self._apply_write(key)

    def _apply_write(self, key: str) -> None:
        m = _RE_VOLT_SET.match(key)
        if m:
            self._ch(int(m.group(1)))["voltage"] = float(m.group(2))
            return
        m = _RE_CURR_SET.match(key)
        if m:
            self._ch(int(m.group(1)))["current"] = float(m.group(2))
            return
        m = _RE_OUT_SET.match(key)
        if m:
            value = m.group(2).upper()
            self._ch(int(m.group(1)))["output"] = value in ("ON", "1")
            return
        # 未识别的写命令忽略（与示波器 mock 行为一致）

    # ---------- 查询 ----------
    def query(self, command: str, timeout: Optional[float] = None) -> str:
        key = command.strip()
        info: dict = {}
        with bus.span("hal", "command", "query", detail=key, source="sim", info=info):
            response = self._apply_query(key)
            info["result"] = response
        return response

    def _apply_query(self, key: str) -> str:
        if key.upper() == "*IDN?":
            return _IDN

        m = _RE_VOLT_GET.match(key)
        if m:
            return "%.4f" % float(self._ch(int(m.group(1)))["voltage"])
        m = _RE_CURR_GET.match(key)
        if m:
            return "%.4f" % float(self._ch(int(m.group(1)))["current"])
        m = _RE_OUT_GET.match(key)
        if m:
            return "ON" if self._ch(int(m.group(1)))["output"] else "OFF"
        m = _RE_MEAS_VOLT.match(key)
        if m:
            return "%.4f" % self._measure_voltage(int(m.group(1)))
        m = _RE_MEAS_CURR.match(key)
        if m:
            return "%.4f" % self._measure_current(int(m.group(1)))
        return ""

    # ---------- 内部 ----------
    def _ch(self, channel: int) -> Dict[str, object]:
        if channel not in self._state:
            raise ValueError("通道号超出范围: %r" % channel)
        return self._state[channel]

    def _measure_voltage(self, channel: int) -> float:
        state = self._ch(channel)
        return float(state["voltage"]) if state["output"] else 0.0

    def _measure_current(self, channel: int) -> float:
        state = self._ch(channel)
        return float(state["current"]) * 0.5 if state["output"] else 0.0
