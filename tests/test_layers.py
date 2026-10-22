"""Transport / Protocol 三层抽象测试（无需硬件）。"""
from autotest.hal.protocol import create_protocol
from autotest.hal.protocol.scpi import ScpiProtocol, parse_ieee_block
from autotest.hal.transport import create_transport
from autotest.hal.transport.tcp import TcpTransport
from autotest.hal.transport.serial import SerialTransport
from autotest.hal.transport.visa import VisaTransport


class FakeTransport:
    def __init__(self, response=b"OK\n", binary=b""):
        self.written = []
        self.response = response
        self.binary = binary
        self.closed = False

    def open(self):
        return None

    def close(self):
        self.closed = True

    def write(self, data):
        self.written.append(data)

    def read(self, size, timeout=None):
        if self.binary:
            chunk, self.binary = self.binary[:size], self.binary[size:]
            return chunk
        return b""

    def read_until(self, terminator, timeout=None):
        return self.response

    @property
    def is_open(self):
        return not self.closed


def test_scpi_protocol_query_and_write():
    t = FakeTransport(response=b"3.300000E+00\n")
    p = ScpiProtocol(t, terminator="\n")
    assert p.query(":MEASure:ITEM? VPP,CHANnel1") == "3.300000E+00"
    assert t.written[0] == b":MEASure:ITEM? VPP,CHANnel1\n"
    p.write(":RUN")
    assert t.written[-1] == b":RUN\n"


def test_scpi_protocol_binary_block():
    payload = b"\x01\x02\x03"
    block = b"#1" + str(len(payload)).encode("ascii") + payload + b"\n"
    t = FakeTransport(binary=block)
    p = ScpiProtocol(t, terminator="\n")
    assert p.query_binary(":WAVeform:DATA?") == payload


def test_parse_ieee_block_still_exported():
    payload, rest = parse_ieee_block(b"#15abcde\n")
    assert payload == b"abcde"
    assert rest == b"\n"


def test_create_transport_kinds():
    tcp = create_transport({"kind": "tcp", "host": "127.0.0.1", "port": 5555})
    assert isinstance(tcp, TcpTransport)
    serial = create_transport({"kind": "serial", "port": "COM3", "baudrate": 115200})
    assert isinstance(serial, SerialTransport)
    visa = create_transport({"kind": "visa", "resource": "TCPIP0::127.0.0.1::INSTR"})
    assert isinstance(visa, VisaTransport)


def test_create_protocol_kinds():
    fake = FakeTransport()
    assert isinstance(create_protocol({"kind": "scpi"}, fake), ScpiProtocol)
    # modbus 为预留接口，但对象应能创建
    assert create_protocol({"kind": "modbus"}, fake).__class__.__name__ == "ModbusProtocol"

