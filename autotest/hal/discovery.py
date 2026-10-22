"""仪器发现：手工连接测试、网段扫描、VISA 枚举、写入仪器注册表。

一期：手工添加 + 连接测试（*IDN?）
二期：网段扫描（TCP 5555/5025 + *IDN?）+ VISA 资源枚举
"""
from __future__ import annotations

import ipaddress
import json
import os
import socket
import struct
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from .protocol import create_protocol
from .transport import create_transport
from .transport.serial import SerialTransport
from .transport.tcp import TcpTransport
from .transport.visa import VisaTransport

DEFAULT_PORTS = (5555, 5025)
MAX_HOSTS = 512


def parse_idn(idn: str) -> Dict[str, str]:
    parts = [p.strip() for p in str(idn or "").split(",")]
    return {
        "idn": str(idn or "").strip(),
        "vendor": parts[0] if len(parts) > 0 else "",
        "model": parts[1] if len(parts) > 1 else "",
        "serial": parts[2] if len(parts) > 2 else "",
        "firmware": parts[3] if len(parts) > 3 else "",
    }


def identify_tcp(host: str, port: int, timeout: float = 0.5) -> Optional[Dict[str, Any]]:
    """探测一个 TCP 端点并读取 *IDN?；成功返回识别信息。"""
    transport = TcpTransport(host, int(port), timeout)
    protocol = create_protocol({"kind": "scpi", "terminator": "\n"}, transport)
    try:
        transport.open()
        idn = protocol.query("*IDN?", timeout=timeout)
        if not idn:
            return None
        result = parse_idn(idn)
        result.update({"host": host, "port": int(port), "transport_kind": "tcp"})
        return result
    except Exception:  # noqa: BLE001
        return None
    finally:
        transport.close()


def local_ipv4() -> str:
    """获取本机用于对外通信的 IPv4（不会真的发包）。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:  # noqa: BLE001
        return "127.0.0.1"
    finally:
        sock.close()


def local_subnet_cidr() -> str:
    try:
        return str(ipaddress.ip_network(local_ipv4() + "/24", strict=False))
    except Exception:  # noqa: BLE001
        return "192.168.1.0/24"


def scan_network(subnet_cidr: str, ports=DEFAULT_PORTS, timeout: float = 0.35,
                 workers: int = 32) -> List[Dict[str, Any]]:
    """扫描网段内的 TCP SCPI 端口并识别仪器。"""
    try:
        network = ipaddress.ip_network(str(subnet_cidr), strict=False)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("无效的网段: %r (%s)" % (subnet_cidr, exc))
    hosts = [str(h) for h in network.hosts()][:MAX_HOSTS]
    ports = tuple(int(p) for p in ports) or DEFAULT_PORTS
    tasks = [(h, p) for h in hosts for p in ports]
    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
        futures = {pool.submit(identify_tcp, h, p, timeout): (h, p) for h, p in tasks}
        for fut in as_completed(futures):
            try:
                item = fut.result()
            except Exception:  # noqa: BLE001
                item = None
            if item:
                results.append(item)
    results.sort(key=lambda r: (r.get("host", ""), r.get("port", 0)))
    return results


def test_connection(config: Dict[str, Any], timeout: float = 3.0) -> Dict[str, Any]:
    """手工连接测试：transport/protocol 配置 -> *IDN? 结果。"""
    transport_cfg = dict(config.get("transport") or config)
    protocol_cfg = dict(config.get("protocol") or {"kind": "scpi"})
    transport_cfg.setdefault("timeout", timeout)
    transport = create_transport(transport_cfg)
    protocol = create_protocol(protocol_cfg, transport)
    try:
        transport.open()
        idn = protocol.query("*IDN?", timeout=timeout)
        result = {"ok": True, "error": ""}
        result.update(parse_idn(idn))
        result.update({"transport_kind": transport_cfg.get("kind", "tcp")})
        return result
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc), "idn": ""}
    finally:
        try:
            transport.close()
        except Exception:  # noqa: BLE001
            pass


def enumerate_visa(timeout_ms: int = 2000) -> List[Dict[str, Any]]:
    """枚举 VISA 资源（USB/LAN/VXI-11/USBTMC）并尝试识别。"""
    try:
        import pyvisa  # type: ignore
    except ImportError:
        return []
    rm = None
    results: List[Dict[str, Any]] = []
    try:
        rm = pyvisa.ResourceManager()
        for resource in list(rm.list_resources()):
            item = {"resource": resource, "idn": "", "transport_kind": "visa", "error": ""}
            try:
                inst = rm.open_resource(resource)
                inst.timeout = int(timeout_ms)
                idn = inst.query("*IDN?").strip()
                inst.close()
                item.update(parse_idn(idn))
            except Exception as exc:  # noqa: BLE001
                item["error"] = "%s: %s" % (type(exc).__name__, exc)
            results.append(item)
    except Exception:  # noqa: BLE001
        return []
    finally:
        if rm is not None:
            try:
                rm.close()
            except Exception:  # noqa: BLE001
                pass
    return results


def make_registry_entry(discovered: Dict[str, Any], instrument_id: str = "",
                        name: str = "", device_type: str = "tcp_scpi",
                        panel: str = "", simulate: bool = False) -> Dict[str, Any]:
    """把发现结果转成 config/instruments.json 的条目。"""
    kind = discovered.get("transport_kind", "tcp")
    iid = instrument_id or ("inst_" + str(discovered.get("host") or discovered.get("resource") or "new"))
    entry: Dict[str, Any] = {
        "id": iid,
        "name": name or discovered.get("model") or iid,
        "model": discovered.get("model", ""),
        "type": device_type,
        "panel": panel,
        "simulate": bool(simulate),
        "visible": True,
        "capabilities": [],
        "transport": {},
        "protocol": {"kind": "scpi", "terminator": "\n"},
    }
    if kind == "tcp":
        entry["transport"] = {
            "kind": "tcp",
            "host": discovered.get("host", ""),
            "port": int(discovered.get("port", 5555)),
            "timeout": 3.0,
        }
    elif kind == "visa":
        entry["transport"] = {
            "kind": "visa",
            "resource": discovered.get("resource", ""),
            "timeout": 3.0,
        }
    return entry


def add_instrument_to_registry(entry: Dict[str, Any], path: str) -> Dict[str, Any]:
    """把仪器条目写入注册表（按 id 或 transport 去重）。"""
    data = {"instruments": []}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh) or {"instruments": []}
    items = data.setdefault("instruments", [])
    new_id = entry.get("id", "")
    new_transport = entry.get("transport", {}) or {}

    def same(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        if a.get("id") and a.get("id") == b.get("id"):
            return True
        ta, tb = a.get("transport", {}) or {}, b.get("transport", {}) or {}
        if ta.get("kind") != tb.get("kind"):
            return False
        if ta.get("kind") == "tcp":
            return ta.get("host") == tb.get("host") and int(ta.get("port", 0)) == int(tb.get("port", 0))
        if ta.get("kind") == "visa":
            return ta.get("resource") == tb.get("resource")
        return False

    for i, existing in enumerate(items):
        if same(existing, entry):
            items[i] = entry
            break
    else:
        items.append(entry)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return entry
