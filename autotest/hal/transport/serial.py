"""串口传输层（pyserial，可选依赖）。

需要串口功能时安装：pip install pyserial
"""
from __future__ import annotations

from typing import Optional

from .base import Transport


class SerialTransport(Transport):
    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 3.0,
                 bytesize: int = 8, parity: str = "N", stopbits: float = 1):
        self.port = port
        self.baudrate = int(baudrate)
        self.timeout = float(timeout)
        self.bytesize = int(bytesize)
        self.parity = parity
        self.stopbits = float(stopbits)
        self._serial = None

    def open(self) -> None:
        try:
            import serial  # type: ignore
        except ImportError as exc:
            raise RuntimeError("串口支持需要安装 pyserial：pip install pyserial") from exc
        self.close()
        self._serial = serial.Serial(
            port=self.port, baudrate=self.baudrate, timeout=self.timeout,
            bytesize=self.bytesize, parity=self.parity, stopbits=self.stopbits,
        )

    def close(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            finally:
                self._serial = None

    @property
    def is_open(self) -> bool:
        return self._serial is not None and bool(getattr(self._serial, "is_open", True))

    def _ensure(self):
        if self._serial is None:
            self.open()

    def write(self, data: bytes) -> None:
        self._ensure()
        self._serial.write(data)
        self._serial.flush()

    def read(self, size: int, timeout: Optional[float] = None) -> bytes:
        self._ensure()
        if timeout is not None:
            self._serial.timeout = timeout
        return self._serial.read(size)

    def read_until(self, terminator: bytes, timeout: Optional[float] = None) -> bytes:
        self._ensure()
        if timeout is not None:
            self._serial.timeout = timeout
        data = bytearray()
        while not data.endswith(terminator):
            ch = self._serial.read(1)
            if not ch:
                break
            data.extend(ch)
        return bytes(data)
