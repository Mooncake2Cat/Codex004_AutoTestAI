"""生成 HTML 测试报告。

两种渲染：
  1) render_acceptance(report)：**验收记录表样式**（分组 + 合并单元格 + 全框线 + 判定着色），
     结构来自 config/report_template.json（阶段5 起为默认输出）；
  2) render(result)：兼容历史的扁平测量表。
Excel 输出接口见 autotest/report/xlsx_export.py（现阶段预留，未实现）。
"""
from __future__ import annotations

import html
import os
from typing import Any, Dict, List, Optional

from ..bus.event_bus import bus
from . import xlsx_export

_CSS = """
body { font-family: "Microsoft YaHei", "Segoe UI", sans-serif; margin: 24px; color: #1f2328; }
h1 { font-size: 20px; text-align: center; margin: 0 0 6px 0; }
.meta { text-align: center; color: #57606a; font-size: 12px; margin: 0 0 4px 0; }
table { border-collapse: collapse; table-layout: fixed; width: 100%; }
table.head { margin-top: 10px; }
table.main { margin-top: 10px; }
th, td { border: 1px solid #333333; padding: 4px 6px; font-size: 12px; vertical-align: middle; word-wrap: break-word; }
thead th { background: #f2f2f2; font-weight: bold; text-align: center; }
table.head th { background: #f2f2f2; font-weight: bold; text-align: center; }
table.head td { text-align: left; }
.center { text-align: center; }
.num { text-align: right; }
.pass { text-align: center; color: #1a7f37; font-weight: bold; }
.fail { text-align: center; color: #cf222e; font-weight: bold; }
.note { color: #57606a; font-size: 11px; margin-top: 8px; }
"""

_ORDER = ["序号", "测试项目", "测试分项", "明细项", "技术指标", "单位", "测试结果", "是否合格"]


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def render_acceptance(report: Dict[str, Any], result: Optional[Dict[str, Any]] = None) -> str:
    """按验收记录表样式渲染（分组 + 合并单元格）。"""
    title = _esc(report.get("title") or "验收记录")
    header_info: List[Dict[str, Any]] = list(report.get("header_info") or [])
    groups: List[Dict[str, Any]] = list(report.get("groups") or [])
    summary = dict(report.get("summary") or {})

    parts: List[str] = []
    parts.append("<!doctype html>")
    parts.append("<html lang='zh-CN'><head><meta charset='utf-8'>")
    parts.append("<title>%s</title>" % title)
    parts.append("<style>%s</style></head><body>" % _CSS)
    parts.append("<h1>%s</h1>" % title)
    parts.append(
        "<p class='meta'>测试编号：%s　状态：%s　合计 %s 项，合格 %s 项，不合格 %s 项</p>"
        % (_esc(report.get("test_id", "")), _esc(report.get("status", "")),
           _esc(summary.get("total", 0)), _esc(summary.get("passed", 0)), _esc(summary.get("failed", 0)))
    )

    # ---------- 表头信息（产品名称/测试地点/产品编号/测试时间） ----------
    if header_info:
        parts.append("<table class='head'><colgroup>")
        for width in (12, 38, 12, 38):
            parts.append("<col style='width:%d%%'>" % width)
        parts.append("</colgroup>")
        for i in range(0, len(header_info), 2):
            row = header_info[i:i + 2]
            parts.append("<tr>")
            for item in row:
                parts.append("<th>%s</th>" % _esc(item.get("label", "")))
                parts.append("<td colspan='%s'>%s</td>"
                             % (int(item.get("span", 3)) and 1, _esc(item.get("value", ""))))
            if len(row) == 1:
                parts.append("<th></th><td></td>")
            parts.append("</tr>")
        parts.append("</table>")

    # ---------- 主表 ----------
    parts.append("<table class='main'><colgroup>")
    for width in (6, 14, 14, 14, 14, 6, 16, 16):
        parts.append("<col style='width:%d%%'>" % width)
    parts.append("</colgroup>")
    parts.append("<thead><tr>")
    parts.append("<th>序号</th><th colspan='3'>测试项目</th>")
    parts.append("<th>技术指标</th><th>单位</th><th>测试结果</th><th>是否合格</th>")
    parts.append("</tr></thead><tbody>")

    for group in groups:
        subs = list(group.get("sub_groups") or [])
        group_rows = sum(len(s.get("rows") or []) for s in subs)
        if group_rows <= 0:
            continue
        first_of_group = True
        for sub in subs:
            rows = list(sub.get("rows") or [])
            if not rows:
                continue
            first_of_sub = True
            for row in rows:
                parts.append("<tr>")
                if first_of_group:
                    parts.append("<td rowspan='%d' class='center'>%s</td>" % (group_rows, _esc(group.get("seq", ""))))
                    parts.append("<td rowspan='%d' class='center'>%s</td>" % (group_rows, _esc(group.get("item", ""))))
                if first_of_sub:
                    parts.append("<td rowspan='%d' class='center'>%s</td>" % (len(rows), _esc(sub.get("sub_item", ""))))
                parts.append("<td class='center'>%s</td>" % _esc(row.get("detail", "")))
                parts.append("<td class='center'>%s</td>" % _esc(row.get("spec", "")))
                parts.append("<td class='center'>%s</td>" % _esc(row.get("unit", "")))
                parts.append("<td class='num'>%s</td>" % _esc(row.get("display", "")))
                passed = bool(row.get("passed"))
                parts.append("<td class='%s'>%s</td>" % ("pass" if passed else "fail",
                                                        "合格" if passed else "不合格"))
                parts.append("</tr>")
                first_of_group = False
                first_of_sub = False
    parts.append("</tbody></table>")
    parts.append("<p class='note'>说明：产品名称 / 测试地点 / 产品编号由用户填写（当前为演示占位值）；"
                 "“是否合格”按技术指标自动判定（支持 ≤ / ≥ / ± / 区间 / 文本型指标）。</p>")
    parts.append("</body></html>")
    return "\n".join(parts)


def render(result: Dict[str, Any]) -> str:
    """兼容历史的扁平测量表。"""
    rows = []
    for m in result.get("measurements", []) or []:
        value = "N/A" if m.get("value") is None else ("%.6g" % m["value"])
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (_esc(m.get("name", "")), value, _esc(m.get("unit", "")),
                       _esc(m.get("instrument_id", "")), _esc(m.get("timestamp", ""))))
    status = _esc(result.get("status", ""))
    test_id = _esc(result.get("test_id", ""))
    message = _esc(result.get("message", ""))
    return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>测试报告 %s</title><style>%s</style></head><body>
<h1>测试报告 %s</h1><p class="meta">状态：%s　说明：%s</p>
<table class="main"><thead><tr><th>测量项</th><th>数值</th><th>单位</th><th>仪器</th><th>时间</th></tr></thead>
<tbody>%s</tbody></table></body></html>""" % (test_id, _CSS, test_id, status, message, "\n".join(rows))


def save(result: Dict[str, Any], path: str,
         template: Optional[Dict[str, Any]] = None,
         acceptance: Optional[Dict[str, Any]] = None) -> str:
    """保存报告。

    - 提供 acceptance（acceptance.build_report 结果）或 template 时，输出**验收记录表样式**；
    - 否则输出历史的扁平测量表。
    """
    if acceptance is None and template is not None:
        from . import acceptance as acc_build
        acceptance = acc_build.build_report(template, result)
    info: Dict[str, Any] = {}
    with bus.span("report", "generate", "html_report", detail=path, info=info):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        content = render_acceptance(acceptance, result) if acceptance else render(result)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        info["result"] = "%s (%d 测量项)" % (path, len(result.get("measurements", []) or []))
    return path


def save_xlsx(result: Dict[str, Any], path: str,
              template: Optional[Dict[str, Any]] = None,
              acceptance: Optional[Dict[str, Any]] = None) -> str:
    """Excel 导出入口（委托 xlsx_export；当前阶段为预留接口）。"""
    if acceptance is None and template is not None:
        from . import acceptance as acc_build
        acceptance = acc_build.build_report(template, result)
    return xlsx_export.save_acceptance_xlsx(acceptance or {}, path, template)