"""能力模型与算法库测试（纯 Python）。"""
import math

from autotest.core import algorithms as alg
from autotest.core import capabilities as cap
from autotest.hal.devices.power_mock import MockPowerSupply
from autotest.hal.mock import MockInstrument


def test_capability_registry():
    actions = cap.all_actions()
    ids = [a["id"] for a in actions]
    assert "power.output_on" in ids
    assert "power.set_voltage" in ids
    assert "scope.measure" in ids
    assert [a["id"] for a in cap.safe_actions("siglent_spd3303x")] == ["power.output_off"]
    assert [a["id"] for a in cap.safe_actions("rigol_dho")] == ["scope.stop"]


def test_capability_defaults_and_params():
    params = cap.default_params("power.set_voltage")
    assert params["channel"] == 1
    assert params["volts"] == 5.0
    assert cap.action("scope.measure")["kind"] == "measure"


def test_execute_power_actions_on_mock():
    power = MockPowerSupply("power1")
    r = cap.execute(power, "power.set_voltage", {"channel": 1, "volts": 12.0})
    assert r["ok"] and r["value"] == 12.0
    r = cap.execute(power, "power.set_current", {"channel": 1, "amps": 1.5})
    assert r["ok"]
    r = cap.execute(power, "power.output_on", {"channel": 1})
    assert r["ok"]
    assert power.query(":CHANnel1:OUTPut?") == "ON"
    r = cap.execute(power, "power.measure_voltage", {"channel": 1})
    assert r["ok"] and abs(r["value"] - 12.0) < 1e-6
    r = cap.execute(power, "power.measure_current", {"channel": 1})
    assert r["ok"] and abs(r["value"] - 0.75) < 1e-6


def test_execute_scope_measure_on_mock():
    scope = MockInstrument("scope1")
    r = cap.execute(scope, "scope.measure", {"item": "vpp", "channel": 2})
    assert r["ok"]
    assert abs(r["value"] - 5.0) < 1e-6
    assert r["unit"] == "V"


def test_execute_unknown_action():
    power = MockPowerSupply("power1")
    r = cap.execute(power, "no.such_action", {})
    assert not r["ok"]


def test_restore_safe_state_turns_outputs_off():
    power = MockPowerSupply("power1", channels=3)
    power.write(":CHANnel1:OUTPut ON")
    power.write(":CHANnel3:OUTPut ON")
    defs = [{"id": "power1", "type": "siglent_spd3303x", "options": {"channels": 3}}]
    done = cap.restore_safe_state({"power1": power}, defs)
    assert len(done) == 3
    assert power.query(":CHANnel1:OUTPut?") == "OFF"
    assert power.query(":CHANnel3:OUTPut?") == "OFF"


def test_algorithms_math():
    assert alg.compute("add", {"a": 2, "b": 3})[1] == 5
    assert alg.compute("sub", {"a": 5, "b": 2})[1] == 3
    assert alg.compute("mul", {"a": 4, "b": 2.5})[1] == 10
    assert alg.compute("div", {"a": 9, "b": 3})[1] == 3
    assert alg.compute("div", {"a": 1, "b": 0})[0] is False


def test_algorithms_waveform():
    vals = [0.0, 1.0, -1.0, 2.0]
    assert alg.compute("vpp", {"values": vals})[1] == 3.0
    assert abs(alg.compute("vavg", {"values": vals})[1] - 0.5) < 1e-9
    assert abs(alg.compute("vrms", {"values": [1, -1, 1, -1]})[1] - 1.0) < 1e-9
    ok, filtered, _ = alg.compute("lowpass", {"values": vals, "alpha": 0.5})
    assert ok and len(filtered) == len(vals)


def test_algorithm_fft_peak():
    n, dt, f = 256, 1e-5, 1000.0
    vals = [math.sin(2 * math.pi * f * i * dt) for i in range(n)]
    ok, value, _ = alg.compute("fft_peak", {"values": vals, "sample_interval": dt})
    assert ok
    assert abs(value - f) / f < 0.1     # 一期算法：误差 < 10%
