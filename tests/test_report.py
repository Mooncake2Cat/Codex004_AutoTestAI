"""验收记录表 HTML 渲染与 Excel 预留接口测试。"""
import os

from autotest.report import acceptance as acc
from autotest.report import html_report as hr
from autotest.report import xlsx_export
from autotest.report.xlsx_export import ExcelExportNotImplemented

TEMPLATE = {
    "title": "验收记录",
    "header_info": [
        {"label": "产品名称", "value": "（演示）产品", "value_span": 3},
        {"label": "测试地点", "value": "（演示）实验室", "value_span": 3},
    ],
    "groups": [
        {"seq": 1, "item": "工作正常性检查", "sub_groups": [
            {"sub_item": "电源输出", "rows": [
                {"detail": "CH1 输出电压", "spec": "5.0±0.1", "unit": "V", "var": "vout"},
                {"detail": "CH1 输出电流", "spec": "≤1.0", "unit": "A", "var": "iout"},
            ]},
        ]},
        {"seq": 2, "item": "波形测量", "sub_groups": [
            {"sub_item": "CH2 波形", "rows": [
                {"detail": "峰峰值 Vpp", "spec": "3.0±0.3", "unit": "V", "var": "vpp"},
            ]},
        ]},
    ],
}

RESULT = {
    "test_id": "t-9", "status": "passed", "finished_at": "2026-09-25T12:00:00",
    "measurements": [
        {"name": "vout", "value": 5.05, "unit": "V"},
        {"name": "iout", "value": 0.5, "unit": "A"},
        {"name": "vpp", "value": 5.0, "unit": "V"},
    ],
}


def test_render_acceptance_layout_and_verdicts():
    report = acc.build_report(TEMPLATE, RESULT)
    html = hr.render_acceptance(report)
    assert "验收记录" in html
    assert "（演示）产品" in html
    assert "工作正常性检查" in html and "波形测量" in html
    assert "rowspan" in html
    assert "合格" in html and "不合格" in html
    assert html.count("<tr>") == 5
    assert report["summary"]["total"] == 3
    assert report["summary"]["failed"] == 1


def test_save_acceptance_html(tmp_path):
    report = acc.build_report(TEMPLATE, RESULT)
    path = str(tmp_path / "report.html")
    saved = hr.save(RESULT, path, acceptance=report)
    assert os.path.exists(saved)
    content = open(saved, encoding="utf-8").read()
    assert "是否合格" in content
    assert "CH1 输出电压" in content


def test_save_with_template_builds_acceptance(tmp_path):
    path = str(tmp_path / "report2.html")
    saved = hr.save(RESULT, path, template=TEMPLATE)
    content = open(saved, encoding="utf-8").read()
    assert "测试项目" in content and "技术指标" in content


def test_xlsx_export_is_reserved():
    assert xlsx_export.is_available() is False
    try:
        xlsx_export.save_acceptance_xlsx({"title": "x"}, "x.xlsx")
        assert False, "应当抛出 ExcelExportNotImplemented"
    except ExcelExportNotImplemented:
        pass