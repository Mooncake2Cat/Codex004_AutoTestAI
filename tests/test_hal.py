import pytest

from autotest.hal.factory import create_instrument
from autotest.hal.mock import MockInstrument
from autotest.hal.rigol_dho import RigolDhoInstrument, parse_measure_value


def test_mock_identify():
    inst = MockInstrument("scope-1")
    idn = inst.query("*IDN?")
    assert idn.startswith("RIGOL TECHNOLOGIES,DHO924S")
    assert "MOCK" in idn  # 明确标注仿真，避免误判为真机


def test_mock_measure_value():
    inst = MockInstrument("scope-1")
    val, raw = inst.measure_value("VPP", 1)
    assert val == pytest.approx(3.3)
    assert raw.startswith("3.300")
    val2, _ = inst.measure_value("FREQUENCY", 1)
    assert val2 == pytest.approx(1000.0)
    val3, _ = inst.measure_value("VPP", 2)
    assert val3 == pytest.approx(5.0)


def test_mock_measure_invalid_no_signal():
    inst = MockInstrument("scope-1")
    val, raw = inst.measure_value("VPP", 3)  # CH3 无信号
    assert val is None
    assert raw == "9.9E+37"


def test_mock_query_measure_parse():
    inst = MockInstrument("scope-1")
    raw = inst.query(":MEASure:ITEM? VPP,CHANnel1")
    assert parse_measure_value(raw) == pytest.approx(3.3)


def test_parse_measure_value():
    assert parse_measure_value("3.300000E+00") == pytest.approx(3.3)
    assert parse_measure_value("9.9E+37") is None   # Rigol 无效测量哨兵
    assert parse_measure_value("9.9E+36") is None
    assert parse_measure_value("nan") is None
    assert parse_measure_value("abc") is None
    assert parse_measure_value("") is None
    assert parse_measure_value(None) is None


def test_factory_creates_mock():
    inst = create_instrument("scope", {"type": "mock"})
    assert isinstance(inst, MockInstrument)


def test_factory_creates_rigol_dho():
    inst = create_instrument(
        "scope",
        {"type": "rigol_dho", "host": "192.168.1.100", "port": 5555},
    )
    assert isinstance(inst, RigolDhoInstrument)
    assert inst.host == "192.168.1.100"
    assert inst.port == 5555
    assert inst.terminator == "\n"


def test_rigol_channel_name_bounds():
    inst = RigolDhoInstrument("127.0.0.1", channels=4)
    assert inst.channel_name(1) == "CHANnel1"
    assert inst.channel_name(4) == "CHANnel4"
    with pytest.raises(ValueError):
        inst.channel_name(5)
    with pytest.raises(ValueError):
        inst.channel_name(0)
