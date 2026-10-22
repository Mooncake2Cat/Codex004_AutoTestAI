"""TCP SCPI 仪器（兼容层）：由 TcpTransport + ScpiProtocol 组合而成。

保留原有 API（initialize/write/query/query_binary/close），因此现有
RigolDhoInstrument / SiglentSpdInstrument / 控制器无需大改即可迁移到三层结构。
"""
from __future__ import annotations

from typing import Optional

from ..bus.event_bus import bus
from .instrument import Instrument
from .protocol.scpi import ScpiProtocol, parse_ieee_block
from .transport.tcp import TcpTransport

__all__ = ["TcpScpiInstrument", "parse_ieee_block"]


class TcpScpiInstrument(Instrument):
    def __init__(self, host: str, port: int = 5025, timeout: float = 2.0, terminator: str = "\n"):
        self.host = host
        self.port = int(port)
        self.timeout = float(timeout)
        self.terminator = terminator
        self._transport = TcpTransport(self.host, self.port, self.timeout)
        self._protocol = ScpiProtocol(self._transport, terminator=terminator)
        self._instrument_id = "%s:%s" % (host, self.port)

    @property
    def is_connected(self) -> bool:
        return self._transport.is_open

    def initialize(self) -> None:
        self.close()
        self._transport.open()

    def _ensure_open(self) -> None:
        if not self.is_connected:
            self.initialize()

    def write(self, command: str) -> None:
        with bus.span("hal", "command", "write", detail=command, source="real"):
            self._protocol.write(command)

    def query(self, command: str, timeout: Optional[float] = None) -> str:
        info: dict = {}
        with bus.span("hal", "command", "query", detail=command, source="real", info=info):
            response = self._protocol.query(command, timeout)
            info["result"] = response
        return response

    def query_binary(self, command: str, timeout: Optional[float] = None) -> bytes:
        info: dict = {}
        with bus.span("hal", "command", "query_binary", detail=command, source="real", info=info):
            payload = self._protocol.query_binary(command, timeout)
            info["result"] = "%d bytes" % len(payload)
        return payload

    def close(self) -> None:
        self._transport.close()

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
