"""电源设备与仪器注册表测试（纯 Python，无 Qt/硬件依赖）。"""
import pytest

from autotest.core.config import load_instruments
from autotest.hal.devices.power_mock import MockPowerSupply
from autotest.hal.devices.power_siglent import SiglentSpdInstrument
from autotest.hal.factory import create_instrument


def test_registry_contains_scope_and_power():
    items = load_instruments()
    ids = [i["id"] for i in items]
    assert "scope1" in ids
    assert "power1" in ids
    power = next(i for i in items if i["id"] == "power1")
    assert power["type"] == "siglent_spd3303x"
    assert power["capabilities"] == ["power"]
    assert power["panel"] == "PowerSupplyInstrument"


def test_factory_creates_simulated_power():
    inst = create_instrument("power1", {"type": "siglent_spd3303x", "simulate": True})
    assert isinstance(inst, MockPowerSupply)


def test_factory_creates_simulated_scope():
    inst = create_instrument("scope1", {"type": "rigol_dho", "simulate": True})
    assert type(inst).__name__ == "MockInstrument"


def test_factory_creates_real_power_with_transport_block():
    inst = create_instrument(
        "power1",
        {"type": "siglent_spd3303x", "transport": {"host": "10.0.0.9", "port": 5025}},
    )
    assert isinstance(inst, SiglentSpdInstrument)
    assert inst.host == "10.0.0.9"
    assert inst.port == 5025


def test_mock_power_set_and_measure():
    inst = MockPowerSupply("power1")
    assert inst.query("*IDN?").startswith("Siglent Technologies,SPD3303X-E")
    inst.write(":CHANnel1:VOLTage 12.0")
    inst.write(":CHANnel1:CURRent 1.5")
    assert inst.query(":CHANnel1:VOLTage?") == "12.0000"
    assert inst.query(":CHANnel1:CURRent?") == "1.5000"
    assert inst.query(":CHANnel1:OUTPut?") == "OFF"
    # 输出关闭时实测为 0
    assert inst.query(":MEASure:VOLTage? CHANnel1") == "0.0000"
    # 打开输出后实测 = 设定电压；电流 = 设定电流 × 0.5（模拟半载）
    inst.write(":CHANnel1:OUTPut ON")
    assert inst.query(":CHANnel1:OUTPut?") == "ON"
    assert inst.query(":MEASure:VOLTage? CHANnel1") == "12.0000"
    assert inst.query(":MEASure:CURRent? CHANnel1") == "0.7500"


def test_mock_power_channel_bounds():
    inst = MockPowerSupply("power1", channels=3)
    with pytest.raises(ValueError):
        inst.query(":MEASure:VOLTage? CHANnel9")
