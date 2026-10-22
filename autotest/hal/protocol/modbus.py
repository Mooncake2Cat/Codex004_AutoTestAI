"""Modbus 协议（接口预留）。

本期只保留接口：等有 Modbus 真机/适配器后，再实现寄存器读写。
"""
from __future__ import annotations

from typing import Optional

from .base import Protocol


class ModbusProtocol(Protocol):
    def __init__(self, transport, unit_id: int = 1):
        self.transport = transport
        self.unit_id = int(unit_id)

    def write(self, command: str) -> None:
        raise NotImplementedError("Modbus 协议接口已预留，待接入真机后实现")

    def query(self, command: str, timeout: Optional[float] = None) -> str:
        raise NotImplementedError("Modbus 协议接口已预留，待接入真机后实现")
