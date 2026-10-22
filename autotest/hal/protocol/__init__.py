"""协议层包：按配置创建 SCPI / Raw / Modbus 协议。"""
from __future__ import annotations

from typing import Any, Dict

from .base import Protocol
from .modbus import ModbusProtocol
from .raw import RawProtocol
from .scpi import ScpiProtocol, parse_ieee_block

__all__ = ["Protocol", "ScpiProtocol", "RawProtocol", "ModbusProtocol",
           "parse_ieee_block", "create_protocol"]


def create_protocol(cfg: Dict[str, Any], transport) -> Protocol:
    kind = str(cfg.get("kind") or cfg.get("type") or "scpi").lower()
    terminator = cfg.get("terminator", "\n")
    if kind == "scpi":
        return ScpiProtocol(transport, terminator=terminator)
    if kind == "raw":
        return RawProtocol(transport, terminator=terminator)
    if kind == "modbus":
        return ModbusProtocol(transport, unit_id=int(cfg.get("unit_id", 1)))
    raise ValueError("未知协议类型: %r" % kind)
