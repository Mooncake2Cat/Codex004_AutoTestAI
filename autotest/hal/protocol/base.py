"""协议层抽象：负责命令的编码/解码与查询语义。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class Protocol(ABC):
    @abstractmethod
    def write(self, command: str) -> None:
        """发送一条命令。"""

    @abstractmethod
    def query(self, command: str, timeout: Optional[float] = None) -> str:
        """发送查询并返回文本响应。"""

    def query_binary(self, command: str, timeout: Optional[float] = None) -> bytes:
        """发送查询并返回二进制响应（默认不支持）。"""
        raise NotImplementedError("该协议不支持二进制查询")
