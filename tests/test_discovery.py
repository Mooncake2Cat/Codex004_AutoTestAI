"""仪器发现测试：本地假 TCP 服务器验证 *IDN? 探测、扫描与注册表写入。"""
import socket
import threading
import time

from autotest.hal import discovery


class FakeScpiServer:
    def __init__(self, idn=b"FakeVendor,FakeModel,SN123,1.0"):
        self.idn = idn
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]
        self.running = True
        self.thread = threading.Thread(target=self._serve, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def _serve(self):
        while self.running:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                break
            with conn:
                data = b""
                while not data.endswith(b"\n"):
                    chunk = conn.recv(1024)
                    if not chunk:
                        break
                    data += chunk
                if b"*IDN?" in data:
                    conn.sendall(self.idn + b"\n")
                else:
                    conn.sendall(b"0\n")

    def close(self):
        self.running = False
        try:
            self.sock.close()
        except OSError:
            pass


def test_identify_tcp_and_scan():
    server = FakeScpiServer().start()
    try:
        item = discovery.identify_tcp("127.0.0.1", server.port, timeout=1.0)
        assert item is not None
        assert item["vendor"] == "FakeVendor"
        assert item["model"] == "FakeModel"
        assert item["serial"] == "SN123"

        results = discovery.scan_network("127.0.0.1/32", ports=(server.port,), timeout=1.0)
        assert len(results) == 1
        assert results[0]["host"] == "127.0.0.1"
        assert results[0]["port"] == server.port
    finally:
        server.close()


def test_test_connection_manual():
    server = FakeScpiServer().start()
    try:
        result = discovery.test_connection({
            "transport": {"kind": "tcp", "host": "127.0.0.1", "port": server.port},
            "protocol": {"kind": "scpi", "terminator": "\n"},
        }, timeout=1.0)
        assert result["ok"] is True
        assert result["model"] == "FakeModel"
    finally:
        server.close()


def test_test_connection_failure():
    result = discovery.test_connection({
        "transport": {"kind": "tcp", "host": "127.0.0.1", "port": 1},
        "protocol": {"kind": "scpi"},
    }, timeout=0.3)
    assert result["ok"] is False
    assert result["error"]


def test_add_to_registry_and_dedupe(tmp_path):
    path = str(tmp_path / "instruments.json")
    entry = {
        "id": "fake1", "name": "Fake", "model": "FakeModel", "type": "tcp_scpi",
        "transport": {"kind": "tcp", "host": "127.0.0.1", "port": 9999},
        "protocol": {"kind": "scpi"},
    }
    discovery.add_instrument_to_registry(entry, path)
    discovery.add_instrument_to_registry(entry, path)   # 同一条目应去重
    other = dict(entry)
    other["id"] = "fake2"
    other["transport"] = {"kind": "tcp", "host": "127.0.0.2", "port": 9999}
    discovery.add_instrument_to_registry(other, path)

    import json
    data = json.load(open(path, encoding="utf-8"))
    assert len(data["instruments"]) == 2


def test_make_registry_entry():
    entry = discovery.make_registry_entry(
        {"host": "192.168.1.10", "port": 5555, "model": "DHO924S", "transport_kind": "tcp"},
        instrument_id="scope2", device_type="rigol_dho", panel="ScopeInstrument")
    assert entry["transport"]["kind"] == "tcp"
    assert entry["transport"]["host"] == "192.168.1.10"
    assert entry["protocol"]["kind"] == "scpi"


def test_enumerate_visa_returns_list():
    result = discovery.enumerate_visa(timeout_ms=100)
    assert isinstance(result, list)
