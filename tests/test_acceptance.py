"""技术指标解析与验收记录表构建测试（纯 Python）。"""
from autotest.report.acceptance import build_report, judge, parse_spec


def test_parse_plus_minus():
    spec = parse_spec("1.2±0.2")
    assert spec["kind"] == "range"
    assert abs(spec["lower"] - 1.0) < 1e-9
    assert abs(spec["upper"] - 1.4) < 1e-9


def test_parse_upper_lower():
    assert parse_spec("≤10")["upper"] == 10
    assert parse_spec("≥30")["lower"] == 30
    assert parse_spec("<10")["upper_inc"] is False
    assert parse_spec(">10")["lower_inc"] is False


def test_parse_range_and_exponent():
    r = parse_spec("9~11")
    assert r["lower"] == 9 and r["upper"] == 11
    e = parse_spec("≤10-6")
    assert e["kind"] == "upper"
    assert abs(e["upper"] - 1e-6) < 1e-12


def test_judge_numeric():
    assert judge("1.2±0.2", 1.2)["passed"] is True
    assert judge("1.2±0.2", 1.5)["passed"] is False
    assert judge("≤10", 10.0)["passed"] is True
    assert judge("≤10", 10.1)["passed"] is False
    assert judge("≥30", 30)["passed"] is True
    assert judge("9~11", 10)["passed"] is True
    assert judge("9~11", 11.5)["passed"] is False
    assert judge("≤10-6", 0.5e-6)["passed"] is True
    assert judge("≤10-6", 2e-6)["passed"] is False


def test_judge_text_and_invalid():
    assert judge("功能正常", "正常")["passed"] is True
    assert judge("功能正常", "异常")["passed"] is False
    assert judge("≤10", None)["passed"] is False
    assert judge("", 5)["passed"] is True


def test_build_report():
    template = {
        "title": "验收记录",
        "header_info": [
            {"label": "产品名称", "value": "演示产品", "value_span": 3},
            {"label": "测试时间", "value": "", "value_span": 3, "auto": "finished_at"},
        ],
        "groups": [
            {"seq": 1, "item": "电源输出", "sub_groups": [
                {"sub_item": "CH1", "rows": [
                    {"detail": "输出电压", "spec": "5.0±0.1", "unit": "V", "var": "vout"},
                    {"detail": "输出电流", "spec": "≤1.0", "unit": "A", "var": "iout"},
                ]},
            ]},
        ],
    }
    result = {
        "test_id": "t-1", "status": "passed", "finished_at": "2026-09-25T10:00:00",
        "measurements": [{"name": "vout", "value": 5.02}, {"name": "iout", "value": 0.5}],
        "verdicts": [],
    }
    report = build_report(template, result)
    assert report["title"] == "验收记录"
    assert report["header_info"][1]["value"] == "2026-09-25T10:00:00"
    rows = report["groups"][0]["sub_groups"][0]["rows"]
    assert rows[0]["passed"] is True
    assert rows[0]["display"] == "5.02"
    assert rows[1]["passed"] is True
    assert report["summary"]["total"] == 2
    assert report["summary"]["all_passed"] is True


def test_build_report_failure_detected():
    template = {"groups": [{"seq": 1, "item": "波形", "sub_groups": [
        {"sub_item": "CH2", "rows": [{"detail": "Vpp", "spec": "3.0±0.3", "unit": "V", "var": "vpp"}]}]}]}
    result = {"measurements": [{"name": "vpp", "value": 5.0}]}
    report = build_report(template, result)
    row = report["groups"][0]["sub_groups"][0]["rows"][0]
    assert row["passed"] is False
    assert report["summary"]["failed"] == 1