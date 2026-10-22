"""SCPI 文本协议（换行分隔、支持 IEEE-488.2 定长块）。"""
from __future__ import annotations

from typing import Optional

from .base import Protocol


def parse_ieee_block(data: bytes):
    """解析 IEEE-488.2 定长块：#<n><len><payload>，返回 (payload, 剩余字节)。"""
    if not data or data[:1] != b"#":
        return None, data
    if len(data) < 2 or not data[1:2].isdigit():
        return None, data
    ndigits = int(data[1:2])
    if ndigits == 0:
        return None, data
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


class ScpiProtocol(Protocol):
    def __init__(self, transport, terminator: str = "\n", encoding: str = "utf-8"):
        self.transport = transport
        self.terminator = terminator
        self.encoding = encoding

    def write(self, command: str) -> None:
        self.transport.write((command + self.terminator).encode(self.encoding))

    def query(self, command: str, timeout: Optional[float] = None) -> str:
        self.write(command)
        data = self.transport.read_until(self.terminator.encode(self.encoding), timeout)
        text = data.decode(self.encoding, errors="replace")
        return text.rstrip("\r\n")

    def query_binary(self, command: str, timeout: Optional[float] = None) -> bytes:
        self.write(command)
        head = self._read_exact(2, timeout)
        if head[:1] != b"#":
            raise IOError("二进制响应缺少 IEEE-488.2 块头: %r" % head)
        ndigits = int(head[1:2])
        length = int(self._read_exact(ndigits, timeout))
        payload = self._read_exact(length, timeout) if length else b""
        # 消费块尾换行（Rigol 会附加换行）
        try:
            self.transport.read(1, 0.2)
        except Exception:  # noqa: BLE001
            pass
        return payload

    def _read_exact(self, count: int, timeout: Optional[float]) -> bytes:
        buf = bytearray()
        while len(buf) < count:
            chunk = self.transport.read(count - len(buf), timeout)
            if not chunk:
                break
            buf.extend(chunk)
        if len(buf) != count:
            raise IOError("读取 %d 字节失败，实际 %d 字节" % (count, len(buf)))
        return bytes(buf)
