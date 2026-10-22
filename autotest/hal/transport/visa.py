"""VISA 传输层（pyvisa，可选依赖）。

支持 USB / LAN / VXI-11 / USBTMC 等 VISA 资源。
"""
from __future__ import annotations

from typing import Optional

from .base import Transport


class VisaTransport(Transport):
    def __init__(self, resource: str, timeout_ms: int = 3000):
        self.resource = resource
        self.timeout_ms = int(timeout_ms)
        self._rm = None
        self._inst = None

    def open(self) -> None:
        try:
            import pyvisa  # type: ignore
        except ImportError as exc:
            raise RuntimeError("VISA 支持需要安装 pyvisa / pyvisa-py") from exc
        self.close()
        self._rm = pyvisa.ResourceManager()
        self._inst = self._rm.open_resource(self.resource)
        self._inst.timeout = self.timeout_ms

    def close(self) -> None:
        if self._inst is not None:
            try:
                self._inst.close()
            finally:
                self._inst = None
        if self._rm is not None:
            try:
                self._rm.close()
            finally:
                self._rm = None

    @property
    def is_open(self) -> bool:
        return self._inst is not None

    def _ensure(self):
        if self._inst is None:
            self.open()

    def write(self, data: bytes) -> None:
        self._ensure()
        self._inst.write_raw(data)

    def read(self, size: int, timeout: Optional[float] = None) -> bytes:
        self._ensure()
        if timeout is not None:
            self._inst.timeout = int(timeout * 1000)
        return bytes(self._inst.read_raw(size))

    def read_until(self, terminator: bytes, timeout: Optional[float] = None) -> bytes:
        self._ensure()
        if timeout is not None:
            self._inst.timeout = int(timeout * 1000)
        data = bytearray()
        while not data.endswith(terminator):
            data.extend(self._inst.read_raw(1))
            if not data:
                break
        return bytes(data)
