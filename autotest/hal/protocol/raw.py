"""原始文本协议（预留）：按终止符收发，不做 SCPI 语义解析。"""
from __future__ import annotations

from typing import Optional

from .base import Protocol


class RawProtocol(Protocol):
    def __init__(self, transport, terminator: str = "\n", encoding: str = "utf-8"):
        self.transport = transport
        self.terminator = terminator
        self.encoding = encoding

    def write(self, command: str) -> None:
        self.transport.write((command + self.terminator).encode(self.encoding))

    def query(self, command: str, timeout: Optional[float] = None) -> str:
        self.write(command)
        data = self.transport.read_until(self.terminator.encode(self.encoding), timeout)
        return data.decode(self.encoding, errors="replace").rstrip("\r\n")
