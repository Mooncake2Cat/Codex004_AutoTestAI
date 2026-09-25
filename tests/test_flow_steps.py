"""流程步骤扩展与运行控制测试（纯 Python，无线程外的依赖）。"""
import threading
import time

from autotest.core.engine import ExecutionControl, ExecutionEngine, FlowStopped
from autotest.hal.devices.power_mock import MockPowerSupply
from autotest.hal.mock import MockInstrument

DEFS = [
    {"id": "scope1", "type": "rigol_dho"},
    {"id": "power1", "type": "siglent_spd3303x", "options": {"channels": 3}},
]

FLOW = {
    "flow_id": "phase4",
    "steps": [
        {"id": "s1", "type": "power_on", "instrument": "power1", "params": {"channel": 1}},
        {"id": "s2", "type": "action", "instrument": "power1", "action": "power.set_voltage",
         "params": {"channel": 1, "volts": 5.0}},
        {"id": "s3", "type": "action", "instrument": "power1", "action": "power.measure_voltage",
         "params": {"channel": 1}, "name": "vout"},
        {"id": "s4", "type": "measure", "instrument": "scope1", "method": "measure_item",
         "params": {"item": "vpp", "channel": 2, "name": "vpp_ch2"}},
        {"id": "s5", "type": "compute", "algorithm": "mul",
         "inputs": {"a": "$vpp_ch2", "b": 2}, "output": "vpp_x2"},
        {"id": "s6", "type": "limit_check", "variable": "vpp_x2",
         "lower": 9.0, "upper": 11.0},
        {"id": "s7", "type": "store", "variable": "vout", "name": "stored_vout", "unit": "V"},
        {"id": "s8", "type": "report", "mapping": {"vpp_ch2": "Vpp列"}},
        {"id": "s9", "type": "power_off", "instrument": "power1", "params": {"channel": 1}},
    ],
}


def _engine(power, scope, control=None):
    return ExecutionEngine({"power1": power, "scope1": scope}, control=control, defs=DEFS)


def test_nine_step_flow_passes():
    power = MockPowerSupply("power1")
    scope = MockInstrument("scope1")
    result = _engine(power, scope).run_flow(FLOW)
    assert result.status == "passed"
    names = [m.name for m in result.measurements]
    assert "vout" in names          # power.measure_voltage
    assert "vpp_ch2" in names       # scope measure
    assert "stored_vout" in names   # store 步骤
    assert len(result.verdicts) == 1
    assert result.verdicts[0]["passed"] is True   # vpp(5.0)x2 = 10，落在 9~11
    assert result.test_conditions.get("report")[0]["vpp_ch2"] == "Vpp列"


def test_limit_check_fails_without_fail_fast():
    power = MockPowerSupply("power1")
    scope = MockInstrument("scope1")
    flow = {
        "flow_id": "limit",
        "steps": [
            {"type": "action", "instrument": "scope1", "action": "scope.measure",
             "params": {"item": "vpp", "channel": 2}, "name": "v"},
            {"type": "limit_check", "variable": "v", "lower": 100, "upper": 200},
        ],
    }
    result = _engine(power, scope).run_flow(flow)
    assert result.status == "passed"                    # 未设置 fail_fast：仅记录判定
    assert result.verdicts[0]["passed"] is False


def test_limit_check_fail_fast_raises():
    power = MockPowerSupply("power1")
    scope = MockInstrument("scope1")
    flow = {
        "flow_id": "limit2",
        "steps": [
            {"type": "action", "instrument": "scope1", "action": "scope.measure",
             "params": {"item": "vpp", "channel": 2}, "name": "v"},
            {"type": "limit_check", "variable": "v", "lower": 100, "upper": 200, "fail_fast": True},
        ],
    }
    result = _engine(power, scope).run_flow(flow)
    assert result.status == "failed"
    assert "限值判定不通过" in result.message


def test_stop_restores_safe_state():
    power = MockPowerSupply("power1")
    scope = MockInstrument("scope1")
    control = ExecutionControl()
    flow = {
        "flow_id": "stop",
        "steps": [
            {"type": "power_on", "instrument": "power1", "params": {"channel": 1}},
            {"type": "wait", "seconds": 1.0},
            {"type": "power_off", "instrument": "power1", "params": {"channel": 1}},
        ],
    }
    box = {}
    engine = _engine(power, scope, control)
    thread = threading.Thread(target=lambda: box.setdefault("r", engine.run_flow(flow)))
    thread.start()
    time.sleep(0.25)
    assert power.query(":CHANnel1:OUTPut?") == "ON"      # 已加电
    control.request_stop()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert box["r"].status == "stopped"
    assert power.query(":CHANnel1:OUTPut?") == "OFF"      # 停止后自动回安全态


def test_pause_does_not_execute_until_resume():
    power = MockPowerSupply("power1")
    scope = MockInstrument("scope1")
    control = ExecutionControl()
    flow = {
        "flow_id": "pause",
        "steps": [
            {"type": "power_on", "instrument": "power1", "params": {"channel": 1}},
            {"type": "wait", "seconds": 0.3},
            {"type": "power_off", "instrument": "power1", "params": {"channel": 1}},
        ],
    }
    box = {}
    engine = _engine(power, scope, control)
    thread = threading.Thread(target=lambda: box.setdefault("r", engine.run_flow(flow)))
    thread.start()
    time.sleep(0.05)         # 第一步（加电）已执行，正在 wait
    control.pause()          # 请求暂停：wait 结束后在步骤边界停住
    time.sleep(0.6)          # 超过 wait 时长
    assert thread.is_alive()                              # 暂停期间流程停住
    assert power.query(":CHANnel1:OUTPut?") == "ON"        # 暂停期间不执行任何动作（power_off 未执行）
    control.resume()
    thread.join(timeout=5)
    assert box["r"].status == "passed"
    assert power.query(":CHANnel1:OUTPut?") == "OFF"      # 继续后执行断电


def test_control_wait_point_raises_when_stopped():
    control = ExecutionControl()
    control.request_stop()
    try:
        control.wait_point()
        assert False, "应当抛出 FlowStopped"
    except FlowStopped:
        pass

