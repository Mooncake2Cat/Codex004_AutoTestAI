"""验收记录表：技术指标解析、合格判定、报表结构构建（纯 Python）。

指标文本解析（参考 Codex005 示例模板的写法）：
    ≤10 / <=10 / ≦10        上限（含）
    ≥30 / >=30 / ≧30        下限（含）
    <10 / >10               上限/下限（不含）
    1.2±0.2                 中心值±容差
    3000±20                 同上
    9~11 / 9-11             区间
    ≤10-6                   视为 10^-6（示例模板的写法）
    功能正常 / 正常 / 合格    文本型判定（值需为 正常/合格/OK/Pass 等）
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Tuple

_NUM = r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"

_PASS_TEXT = {"正常", "合格", "通过", "ok", "pass", "true", "yes", "y", "是", "功能正常"}


def _f(text: str) -> Optional[float]:
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return None


def parse_spec(text: Any) -> Dict[str, Any]:
    """把技术指标文本解析为上下限。返回 {kind, lower, upper, lower_inc, upper_inc, note}。"""
    raw = "" if text is None else str(text).strip()
    if not raw:
        return {"kind": "none", "lower": None, "upper": None,
                "lower_inc": True, "upper_inc": True, "note": "无指标"}

    s = raw.replace("≦", "≤").replace("≧", "≥").replace("－", "-").replace("—", "-")

    # 10-6 / 10^-6 形式的科学计数（示例模板中 ≤10-6 表示 ≤1e-6）
    m = re.fullmatch(r"(≤|>=|≥|<=|<|>)?\s*10\s*(?:\^)?\s*-\s*(\d+)", s)
    if m:
        op = m.group(1) or ""
        exp = int(m.group(2))
        val = 10.0 ** (-exp)
        if op in ("≥", ">=", ">",):
            return {"kind": "lower", "lower": val, "upper": None,
                    "lower_inc": op != ">", "upper_inc": True, "note": "解析为 ≥1e-%d" % exp}
        return {"kind": "upper", "lower": None, "upper": val,
                "lower_inc": True, "upper_inc": op not in ("<",), "note": "解析为 ≤1e-%d" % exp}

    # a±b
    m = re.fullmatch(r"\s*(%s)\s*[±]\s*(%s)\s*" % (_NUM, _NUM), s)
    if m:
        center, tol = _f(m.group(1)), _f(m.group(2))
        if center is not None and tol is not None:
            return {"kind": "range", "lower": center - abs(tol), "upper": center + abs(tol),
                    "lower_inc": True, "upper_inc": True, "note": "%g ± %g" % (center, tol)}

    # 区间 a~b / a-b（避免把科学计数的负号当分隔符）
    m = re.fullmatch(r"\s*(%s)\s*[~～]\s*(%s)\s*" % (_NUM, _NUM), s)
    if not m:
        m = re.fullmatch(r"\s*(%s)\s+[-]\s+(%s)\s*" % (_NUM, _NUM), s)
    if m:
        lo, hi = _f(m.group(1)), _f(m.group(2))
        if lo is not None and hi is not None:
            if lo > hi:
                lo, hi = hi, lo
            return {"kind": "range", "lower": lo, "upper": hi,
                    "lower_inc": True, "upper_inc": True, "note": "区间 %g~%g" % (lo, hi)}

    # ≤/≥/</>
    m = re.fullmatch(r"\s*(≤|>=|≥|<=|<|>)\s*(%s)\s*" % _NUM, s)
    if m:
        op, val = m.group(1), _f(m.group(2))
        if val is not None:
            if op in ("≥", ">=", ">",):
                return {"kind": "lower", "lower": val, "upper": None,
                        "lower_inc": op in ("≥", ">="), "upper_inc": True, "note": "下限"}
            return {"kind": "upper", "lower": None, "upper": val,
                    "lower_inc": True, "upper_inc": op in ("≤", "<="), "note": "上限"}

    # 纯数字：视为等值±0
    val = _f(s)
    if val is not None:
        return {"kind": "range", "lower": val, "upper": val,
                "lower_inc": True, "upper_inc": True, "note": "等值"}

    return {"kind": "text", "lower": None, "upper": None,
            "lower_inc": True, "upper_inc": True, "note": "文本型指标"}


def judge(spec_text: Any, value: Any) -> Dict[str, Any]:
    """按技术指标判定。返回 {passed, kind, lower, upper, note, value}。"""
    spec = parse_spec(spec_text)
    kind = spec["kind"]
    out = {"passed": False, "kind": kind, "lower": spec["lower"], "upper": spec["upper"],
           "note": spec["note"], "value": value}

    if kind == "none":
        out["passed"] = value is not None
        return out

    if kind == "text":
        text = ("" if value is None else str(value)).strip().lower()
        out["passed"] = text in _PASS_TEXT
        return out

    num = None
    if isinstance(value, bool):
        num = 1.0 if value else 0.0
    else:
        num = _f(value)
    if num is None:
        out["passed"] = False
        out["note"] = spec["note"] + "（值无效）"
        return out

    passed = True
    if spec["lower"] is not None:
        passed = passed and (num >= spec["lower"] if spec["lower_inc"] else num > spec["lower"])
    if spec["upper"] is not None:
        passed = passed and (num <= spec["upper"] if spec["upper_inc"] else num < spec["upper"])
    out["passed"] = bool(passed)
    return out


# ----------------------------------------------------------------------------
# 报表结构构建
# ----------------------------------------------------------------------------

def _value_of(name: str, values: Dict[str, Any]) -> Any:
    if not name:
        return None
    if name in values:
        return values[name]
    return None


def build_report(template: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """把模板 + 测试结果合并为可渲染结构。

    result: TestResult.to_dict() 形式（measurements / verdicts / test_conditions / finished_at）。
    """
    values: Dict[str, Any] = {}
    for m in result.get("measurements", []) or []:
        values[m.get("name", "")] = m.get("value")
    for v in result.get("verdicts", []) or []:
        if v.get("name"):
            values[v["name"]] = v.get("value")
    values.update(result.get("variables", {}) or {})

    # 表头信息：模板值优先；auto=finished_at 时使用结果时间（演示阶段不做实际填写）
    header = []
    for item in template.get("header_info", []) or []:
        label = item.get("label", "")
        value = item.get("value", "")
        if item.get("auto") == "finished_at":
            value = result.get("finished_at") or value
        header.append({"label": label, "value": value, "span": int(item.get("value_span", 3))})

    groups_out: List[Dict[str, Any]] = []
    for group in template.get("groups", []) or []:
        subs_out = []
        for sub in group.get("sub_groups", []) or []:
            rows_out = []
            for row in sub.get("rows", []) or []:
                var = row.get("var", "")
                raw_value = _value_of(var, values)
                verdict = judge(row.get("spec", ""), raw_value)
                rows_out.append({
                    "detail": row.get("detail", ""),
                    "spec": row.get("spec", ""),
                    "unit": row.get("unit", ""),
                    "var": var,
                    "value": raw_value,
                    "display": _fmt_value(raw_value),
                    "passed": bool(verdict.get("passed")),
                    "verdict_note": verdict.get("note", ""),
                    "lower": verdict.get("lower"),
                    "upper": verdict.get("upper"),
                    "kind": verdict.get("kind"),
                })
            subs_out.append({"sub_item": sub.get("sub_item", ""), "rows": rows_out})
        groups_out.append({
            "seq": group.get("seq", ""),
            "item": group.get("item", ""),
            "sub_groups": subs_out,
        })

    total = sum(len(s["rows"]) for g in groups_out for s in g["sub_groups"])
    passed = sum(1 for g in groups_out for s in g["sub_groups"] for r in s["rows"] if r["passed"])
    return {
        "title": template.get("title", "验收记录"),
        "columns": template.get("columns", ["序号", "测试项目", "测试分项", "明细项", "技术指标", "单位", "测试结果", "是否合格"]),
        "header_info": header,
        "groups": groups_out,
        "test_id": result.get("test_id", ""),
        "status": result.get("status", ""),
        "summary": {"total": total, "passed": passed, "failed": total - passed,
                    "all_passed": total > 0 and passed == total},
    }


def _fmt_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "正常" if value else "异常"
    if isinstance(value, float):
        if value != 0 and (abs(value) >= 1e6 or abs(value) < 1e-3):
            return "%.4g" % value
        return ("%.4f" % value).rstrip("0").rstrip(".")
    return str(value)
