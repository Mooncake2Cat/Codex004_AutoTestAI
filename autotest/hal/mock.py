"""模拟仪器：无真机时用于链路自检、UI 演示与自动化测试。

v2：升级为“DHO924S 示波器仿真器”。它能以文本方式响应示波器 SCPI：
  - *IDN?                    → 返回 Rigol 风格识别串（序列号带 MOCK 前缀，避免误判为真机）
  - :MEASure:ITEM? <item>,CHANnel<n> → 按通道仿真自动测量值（科学计数法返回）
  - CH1/CH2 有信号；CH3/CH4 无信号，返回 9.9E+37（演示“测不出”场景）
通用旧命令（POW?/FREQ:CW?）不再支持，回归到通用 query 方法时会解析为无效。
"""
from __future__ import annotations

import math
import re
from typing import Dict, Optional, Tuple

from .instrument import Instrument

_IDN = "RIGOL TECHNOLOGIES,DHO924S,MOCK-SN-000001,9.9.9"
_INVALID = "9.9E+37"

# 通道仿真参数：item(规范化大写) -> 值
_SIM = {
    1: {  # 1 kHz 正弦，Vpp=3.3 V
        "VPP": 3.3, "VRMS": 3.3 / (2 * math.sqrt(2)), "VMAX": 1.65, "VMIN": -1.65,
        "VAVG": 0.0, "FREQUENCY": 1000.0, "FREQ": 1000.0, "PERIOD": 1.0e-3, "PER": 1.0e-3,
    },
    2: {  # 5 kHz 方波，Vpp=5.0 V
        "VPP": 5.0, "VRMS": 2.5, "VMAX": 2.5, "VMIN": -2.5, "VAVG": 0.0,
        "FREQUENCY": 5000.0, "FREQ": 5000.0, "PERIOD": 2.0e-4, "PER": 2.0e-4,
    },
}

_MEASURE_RE = re.compile(r"^:MEASure:ITEM\?\s+([A-Za-z]+)\s*,\s*CHANnel([1-9][0-9]*)$", re.IGNORECASE)


def _fmt(value: float) -> str:
    """Rigol 风格科学计数法返回，如 3.300000E+00 / 9.9E+37。"""
    return "%.6E" % value


class MockInstrument(Instrument):
    def __init__(self, instrument_id: str = "mock-1"):
        self._instrument_id = instrument_id

    def initialize(self) -> None:
        return None

    def write(self, command: str) -> None:
        # 仿真器不维护状态；:RUN/:STOP 等写命令直接忽略
        return None

    def query(self, command: str, timeout: Optional[float] = None) -> str:
        key = command.strip()
        if key.upper() == "*IDN?":
            return _IDN

        m = _MEASURE_RE.match(key)
        if m:
            item = m.group(1).upper()
            channel = int(m.group(2))
            value = self._sim_measure(item, channel)
            return _fmt(value) if value is not None else _INVALID

        # 未识别的查询返回空串（方法层解析为无效，便于暴露流程中的拼写问题）
        return ""

    def measure_value(self, item: str, channel: int = 1) -> Tuple[Optional[float], str]:
        """与真机驱动对称的接口：返回 (value, raw)。"""
        m = _MEASURE_RE.match(":MEASure:ITEM? %s,CHANnel%d" % (item, channel))
        if not m:
            raise ValueError("非法测量命令")
        item = m.group(1).upper()
        channel = int(m.group(2))
        value = self._sim_measure(item, channel)
        return (value, _fmt(value)) if value is not None else (None, _INVALID)

    def _sim_measure(self, item: str, channel: int) -> Optional[float]:
        if channel not in _SIM:
            return None  # 无信号通道：返回无效（9.9E+37）
        table = _SIM[channel]
        value = table.get(item)
        if value is None:
            # 有信号但未仿真该项 -> 无效，避免给出误导值
            return None
        return value

    def close(self) -> None:
        return None

