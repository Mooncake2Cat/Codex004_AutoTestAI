from autotest.core.models import Measurement, TestResult


def test_measurement_roundtrip():
    m = Measurement(name="output_power", value=-12.34, unit="dBm", instrument_id="spec")
    d = m.to_dict()
    m2 = Measurement.from_dict(d)
    assert m2.name == "output_power"
    assert m2.value == -12.34
    assert m2.unit == "dBm"


def test_result_roundtrip():
    r = TestResult(test_id="t1", dut_info={"dut": "PA-5G-001"})
    r.measurements.append(Measurement(name="p", value=1.0, unit="dBm"))
    r.finish("passed", "ok")
    d = r.to_dict()
    r2 = TestResult.from_dict(d)
    assert r2.test_id == "t1"
    assert r2.status == "passed"
    assert r2.measurements[0].name == "p"
