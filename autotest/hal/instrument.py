"""仪器抽象接口定义。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class Instrument(ABC):
    """所有仪器/板卡驱动的统一接口。

    原型阶段只覆盖"网口通讯"仪器，因此以 SCPI 文本读写为核心。
    """

    @abstractmethod
    def initialize(self) -> None:
        """打开/连接仪器。"""

    @abstractmethod
    def write(self, command: str) -> None:
        """发送命令。"""

    @abstractmethod
    def query(self, command: str, timeout: Optional[float] = None) -> str:
        """发送命令并读取响应。"""

    @abstractmethod
    def close(self) -> None:
        """关闭连接。"""

    @property
    def instrument_id(self) -> str:
        return getattr(self, "_instrument_id", "")
