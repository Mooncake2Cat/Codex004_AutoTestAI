"""仪器工厂：根据配置（注册表条目）创建仪器实例。

支持的类型：
  - mock              通用模拟仪器（示波器仿真）
  - rigol_dho         Rigol DHO900 系列（DHO924S）网口示波器
  - siglent_spd3303x  鼎阳 SPD3303X-E 三路可编程直流电源
  - tcp_scpi          通用 TCP SCPI 仪器（兜底）

配置格式（推荐，见 config/instruments.json）：
  {"id":"scope1","type":"rigol_dho","simulate":true,
   "transport":{"host":"...","port":5555,"timeout":3.0,"terminator":"\n"},
   "options":{"channels":4}}
同时兼容旧的扁平写法（host/port 直接放在配置顶层）。
"""
from __future__ import annotations

from typing import Any, Dict

from .devices.power_mock import MockPowerSupply
from .devices.power_siglent import SiglentSpdInstrument
from .instrument import Instrument
from .mock import MockInstrument
from .rigol_dho import RigolDhoInstrument
from .scpi import TcpScpiInstrument


def create_instrument(instrument_id: str, config: Dict[str, Any]) -> Instrument:
    kind = config.get("type", "mock")
    simulate = bool(config.get("simulate", False))
    transport = config.get("transport", {}) or {}
    options = config.get("options", {}) or {}

    host = transport.get("host", config.get("host"))
    port = transport.get("port", config.get("port"))
    timeout = transport.get("timeout", config.get("timeout", 3.0))
    terminator = transport.get("terminator", config.get("terminator", "\n"))

    if kind == "mock":
        return MockInstrument(instrument_id=instrument_id)

    if kind == "rigol_dho":
        if simulate:
            return MockInstrument(instrument_id=instrument_id)
        return RigolDhoInstrument(
            host=host or "192.168.10.16",
            port=port or 5555,
            timeout=timeout,
            terminator=terminator,
            channels=options.get("channels", config.get("channels", 4)),
            model=config.get("model", "DHO924S"),
        )

    if kind == "siglent_spd3303x":
        if simulate:
            return MockPowerSupply(
                instrument_id=instrument_id,
                channels=options.get("channels", config.get("channels", 3)),
            )
        return SiglentSpdInstrument(
            host=host or "192.168.1.50",
            port=port or 5025,
            timeout=timeout,
            terminator=terminator,
            channels=options.get("channels", config.get("channels", 3)),
            model=config.get("model", "SPD3303X-E"),
        )

    if kind == "tcp_scpi":
        return TcpScpiInstrument(
            host=host or "127.0.0.1",
            port=port or 5025,
            timeout=timeout,
            terminator=terminator,
        )

    raise ValueError("未知仪器类型: %r" % kind)
