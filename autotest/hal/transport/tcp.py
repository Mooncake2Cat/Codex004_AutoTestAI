"""TCP Socket 传输层。"""
from __future__ import annotations

import socket
from typing import Optional

from .base import Transport


class TcpTransport(Transport):
    def __init__(self, host: str, port: int, timeout: float = 3.0):
        self.host = host
        self.port = int(port)
        self.timeout = float(timeout)
        self._sock: Optional[socket.socket] = None

    def open(self) -> None:
        self.close()
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._sock.settimeout(self.timeout)

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    @property
    def is_open(self) -> bool:
        return self._sock is not None

    def _ensure(self):
        if self._sock is None:
            self.open()

    def write(self, data: bytes) -> None:
        self._ensure()
        self._sock.sendall(data)

    def read(self, size: int, timeout: Optional[float] = None) -> bytes:
        self._ensure()
        old = self._sock.gettimeout()
        if timeout is not None:
            self._sock.settimeout(timeout)
        try:
            return self._sock.recv(size)
        finally:
            if timeout is not None:
                self._sock.settimeout(old)

    def read_until(self, terminator: bytes, timeout: Optional[float] = None) -> bytes:
        self._ensure()
        old = self._sock.gettimeout()
        if timeout is not None:
            self._sock.settimeout(timeout)
        data = bytearray()
        try:
            while not data.endswith(terminator):
                chunk = self._sock.recv(4096)
                if not chunk:
                    break
                data.extend(chunk)
        finally:
            if timeout is not None:
                self._sock.settimeout(old)
        return bytes(data)
