"""TCP 原始 socket SCPI 仪器驱动。

适用于多数支持 5025 端口 SCPI 文本协议的网口仪器。
"""
from __future__ import annotations

import socket
from typing import Optional

from .instrument import Instrument


def parse_ieee_block(data: bytes):
    """解析 IEEE-488.2 定长块：``#<n><len><payload>``。

    返回 (payload, 剩余字节)。若数据不是定长块（例如纯文本），
    则返回 (None, 原数据)，由调用方决定如何处理。
    """
    if not data or data[:1] != b"#":
        return None, data
    if len(data) < 2 or not data[1:2].isdigit():
        return None, data
    ndigits = int(data[1:2])
    if ndigits == 0:
        return None, data  # 不定长块（#0），本驱动暂不支持
    header = 2 + ndigits
    if len(data) < header:
        return None, data
    try:
        length = int(data[2:header])
    except ValueError:
        return None, data
    end = header + length
    if len(data) < end:
        return None, data
    return data[header:end], data[end:]


class TcpScpiInstrument(Instrument):
    def __init__(self, host: str, port: int = 5025, timeout: float = 2.0, terminator: str = "\n"):
        self.host = host
        self.port = int(port)
        self.timeout = timeout
        self.terminator = terminator
        self._sock: Optional[socket.socket] = None
        self._instrument_id = "%s:%s" % (host, port)

    def initialize(self) -> None:
        self.close()
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._sock.settimeout(self.timeout)

    def write(self, command: str) -> None:
        self._ensure_open()
        self._sock.sendall((command + self.terminator).encode("utf-8"))

    def query(self, command: str, timeout: Optional[float] = None) -> str:
        self._ensure_open()
        if timeout is not None:
            self._sock.settimeout(timeout)
        self.write(command)
        data = bytearray()
        term = self.terminator.encode("utf-8")
        while not data.endswith(term):
            chunk = self._sock.recv(4096)
            if not chunk:
                break
            data.extend(chunk)
        return bytes(data).decode("utf-8", errors="replace").rstrip(self.terminator)

    def query_binary(self, command: str, timeout: Optional[float] = None) -> bytes:
        """发送查询并读取 IEEE-488.2 定长块（用于 :WAVeform:DATA? 等二进制返回）。

        返回 payload 字节（不含块头与结尾换行）。
        """
        self._ensure_open()
        if timeout is not None:
            self._sock.settimeout(timeout)
        self.write(command)
        head = self._recv_exact(2)
        if head[:1] != b"#":
            raise IOError("二进制响应缺少 IEEE-488.2 块头: %r" % head)
        ndigits = int(head[1:2])
        length = int(self._recv_exact(ndigits))
        payload = self._recv_exact(length) if length else b""
        # 消费块尾的换行（Rigol 会附加换行），避免污染下一次查询
        try:
            self._sock.settimeout(0.2)
            self._sock.recv(1)
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._sock.settimeout(self.timeout)
        return payload

    def _recv_exact(self, count: int) -> bytes:
        buf = bytearray()
        while len(buf) < count:
            chunk = self._sock.recv(count - len(buf))
            if not chunk:
                break
            buf.extend(chunk)
        if len(buf) != count:
            raise IOError("读取 %d 字节失败，实际 %d 字节" % (count, len(buf)))
        return bytes(buf)

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def _ensure_open(self) -> None:
        if self._sock is None:
            self.initialize()

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


