"""仪器工厂：根据配置创建仪器实例。

支持的仪器类型：
  - mock        模拟仪器（DHO924S 仿真器，用于无真机演示/自检）
  - rigol_dho   Rigol DHO900 系列（含 DHO924S）网口示波器，raw SCPI TCP 5555
  - tcp_scpi    通用 TCP SCPI 仪器（其它网口仪器兜底）
"""
from __future__ import annotations

from typing import Any, Dict

from .instrument import Instrument
from .mock import MockInstrument
from .rigol_dho import RigolDhoInstrument
from .scpi import TcpScpiInstrument


def create_instrument(instrument_id: str, config: Dict[str, Any]) -> Instrument:
    kind = config.get("type", "mock")

    if kind == "mock":
        return MockInstrument(instrument_id=instrument_id)

    if kind == "rigol_dho":
        return RigolDhoInstrument(
            host=config.get("host", "192.168.1.100"),
            port=config.get("port", 5555),
            timeout=config.get("timeout", 3.0),
            terminator=config.get("terminator", "\n"),
            channels=config.get("channels", 4),
            model=config.get("model", "DHO924S"),
        )

    if kind == "tcp_scpi":
        return TcpScpiInstrument(
            host=config.get("host", "127.0.0.1"),
            port=config.get("port", 5025),
            timeout=config.get("timeout", 2.0),
            terminator=config.get("terminator", "\n"),
        )

    raise ValueError("未知仪器类型: %r" % kind)
