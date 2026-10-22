"""传输层包：按配置创建 TCP / Serial / VISA 传输。"""
from __future__ import annotations

from typing import Any, Dict

from .base import Transport
from .serial import SerialTransport
from .tcp import TcpTransport
from .visa import VisaTransport

__all__ = ["Transport", "TcpTransport", "SerialTransport", "VisaTransport", "create_transport"]


def create_transport(cfg: Dict[str, Any]) -> Transport:
    kind = str(cfg.get("kind") or cfg.get("type") or "tcp").lower()
    if kind in ("tcp", "socket", "tcp_scpi"):
        return TcpTransport(
            host=cfg.get("host", "127.0.0.1"),
            port=int(cfg.get("port", 5555)),
            timeout=float(cfg.get("timeout", 3.0)),
        )
    if kind in ("serial", "com"):
        return SerialTransport(
            port=cfg.get("port") or cfg.get("device") or "COM1",
            baudrate=int(cfg.get("baudrate", 9600)),
            timeout=float(cfg.get("timeout", 3.0)),
            bytesize=int(cfg.get("bytesize", 8)),
            parity=str(cfg.get("parity", "N")),
            stopbits=float(cfg.get("stopbits", 1)),
        )
    if kind == "visa":
        return VisaTransport(
            resource=cfg.get("resource") or cfg.get("address") or "",
            timeout_ms=int(float(cfg.get("timeout", 3.0)) * 1000),
        )
    raise ValueError("未知传输类型: %r" % kind)
