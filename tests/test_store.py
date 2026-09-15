from autotest.core.models import Measurement, TestResult
from autotest.data.store import LocalStore


def test_save_and_get_result(tmp_path):
    db = tmp_path / "test.db"
    result = TestResult(test_id="t-123", dut_info={"dut": "PA-5G-001"})
    result.measurements.append(Measurement(name="power", value=-12.3, unit="dBm", instrument_id="spec"))
    result.finish("passed", "ok")

    with LocalStore(str(db)) as store:
        store.save_result(result)

    with LocalStore(str(db)) as store:
        got = store.get_result("t-123")
        assert got is not None
        assert got["test_id"] == "t-123"
        assert got["status"] == "passed"
        assert got["measurements"][0]["value"] == -12.3
        assert len(store.list_results()) == 1
