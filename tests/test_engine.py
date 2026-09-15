from autotest.core.engine import ExecutionEngine
from autotest.hal.mock import MockInstrument

FLOW = {
    "flow_id": "dho-demo",
    "dut_info": {"dut": "DUT-1"},
    "test_conditions": {},
    "steps": [
        {"id": "s1", "type": "measure", "instrument": "scope", "method": "identify", "params": {"name": "instrument_id"}},
        {"id": "s2", "type": "loop", "count": 3, "body": [
            {"id": "s2.1", "type": "measure", "instrument": "scope", "method": "measure_item",
             "params": {"item": "vpp", "channel": 1, "name": "ch1_vpp"}},
        ]},
        {"id": "s3", "type": "measure", "instrument": "scope", "method": "measure_item",
         "params": {"item": "frequency", "channel": 1, "name": "ch1_freq"}},
        {"id": "s4", "type": "measure", "instrument": "scope", "method": "measure_item",
         "params": {"item": "vrms", "channel": 1, "name": "ch1_vrms"}},
        {"id": "s5", "type": "measure", "instrument": "scope", "method": "measure_item",
         "params": {"item": "vpp", "channel": 3, "name": "ch3_vpp"}},
    ],
}


def test_run_flow_passes():
    engine = ExecutionEngine({"scope": MockInstrument("scope-1")})
    result = engine.run_flow(FLOW)
    assert result.status == "passed"
    # identify(1) + loop 3 次 + freq + vrms + ch3 vpp = 7
    assert len(result.measurements) == 7
    assert result.measurements[0].raw_value.startswith("RIGOL TECHNOLOGIES,DHO924S,MOCK")
    assert result.measurements[1].value == 3.3
    # CH3 无信号：值应为 None（无效 9.9E+37）
    last = result.measurements[-1]
    assert last.name == "ch3_vpp"
    assert last.value is None
    assert last.raw_value == "9.9E+37"


def test_missing_instrument_fails_gracefully():
    engine = ExecutionEngine({})
    result = engine.run_flow(FLOW)
    assert result.status == "failed"
    assert "未配置的仪器" in result.message
