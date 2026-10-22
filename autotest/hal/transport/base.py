"""传输层抽象：只负责字节的收发，不关心协议内容。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class Transport(ABC):
    @abstractmethod
    def open(self) -> None:
        """打开/建立连接。"""

    @abstractmethod
    def close(self) -> None:
        """关闭连接。"""

    @abstractmethod
    def write(self, data: bytes) -> None:
        """发送原始字节。"""

    @abstractmethod
    def read(self, size: int, timeout: Optional[float] = None) -> bytes:
        """读取最多 size 字节。"""

    @abstractmethod
    def read_until(self, terminator: bytes, timeout: Optional[float] = None) -> bytes:
        """读取直到遇到终止符（返回内容包含终止符）。"""

    @property
    @abstractmethod
    def is_open(self) -> bool:
        """连接是否已打开。"""
