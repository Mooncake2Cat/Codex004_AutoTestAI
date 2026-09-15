"""生成 HTML 测试报告。"""
from __future__ import annotations

import html
import os
from typing import Any, Dict

from ..bus.event_bus import bus


def render(result: Dict[str, Any]) -> str:
    measurements = result.get("measurements", [])
    rows = []
    for m in measurements:
        value = "N/A" if m.get("value") is None else ("%.6g" % m["value"])
        rows.append(
            "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (
                html.escape(str(m.get("name", ""))),
                value,
                html.escape(str(m.get("unit", ""))),
                html.escape(str(m.get("instrument_id", ""))),
                html.escape(str(m.get("timestamp", ""))),
            )
        )

    status = html.escape(str(result.get("status", "")))
    test_id = html.escape(str(result.get("test_id", "")))
    message = html.escape(str(result.get("message", "")))

    return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>测试报告 {test_id}</title>
<style>
  body {{ font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; margin: 24px; color: #222; }}
  h1 {{ font-size: 20px; }}
  .status-passed {{ color: #1a7f37; font-weight: 700; }}
  .status-failed {{ color: #c62828; font-weight: 700; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 13px; }}
  th {{ background: #f5f5f5; }}
</style>
</head>
<body>
<h1>测试报告 {test_id}</h1>
<p>状态：<span class="status-{status}">{status}</span></p>
<p>说明：{message}</p>
<table>
  <thead>
    <tr><th>测量项</th><th>数值</th><th>单位</th><th>仪器</th><th>时间</th></tr>
  </thead>
  <tbody>
{rows}
  </tbody>
</table>
</body>
</html>
""".format(test_id=test_id, status=status, message=message, rows="\n".join(rows))


def save(result: Dict[str, Any], path: str) -> str:
    info: Dict[str, Any] = {}
    # 事件总线：报告生成
    with bus.span("report", "generate", "html_report", detail=path, info=info):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        content = render(result)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        info["result"] = "%s (%d 测量项)" % (path, len(result.get("measurements", [])))
    return path

