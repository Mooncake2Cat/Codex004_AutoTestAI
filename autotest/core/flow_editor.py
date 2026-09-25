"""流程编辑模型（纯函数，供界面与测试使用；阶段4）。

编辑范围（一期）：
  - 只编辑流程的**顶层步骤**（loop/branch 内部子步骤仅展示，不在此编辑）；
  - 步骤参数由能力模型自动生成（action 类步骤），其余步骤用内置参数描述。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import algorithms as alg
from . import capabilities as cap

# 内置步骤类型（非能力动作）
BUILTIN_STEPS = [
    {"type": "wait", "label": "等待"},
    {"type": "compute", "label": "波形计算"},
    {"type": "limit_check", "label": "限值判定"},
    {"type": "store", "label": "存库"},
    {"type": "report", "label": "填报表"},
    {"type": "loop", "label": "循环"},
    {"type": "branch", "label": "条件分支"},
]

_MEASURE_ITEMS = ["vpp", "vrms", "vavg", "vmax", "vmin", "freq", "per", "rtime", "ftime", "pduty"]
_PARAM_TYPES = {
    "channel": "int", "volts": "float", "amps": "float",
    "seconds_per_div": "float", "volts_per_div": "float",
    "seconds": "float", "lower": "float", "upper": "float",
    "item": "str", "algorithm": "str", "output": "str", "variable": "str",
    "a": "str", "b": "str",
}


def steps(flow: Dict[str, Any]) -> List[Dict[str, Any]]:
    return flow.setdefault("steps", [])


# ----------------------------------------------------------------------------
# 展示
# ----------------------------------------------------------------------------

def summarize(flow: Dict[str, Any]) -> List[Dict[str, Any]]:
    """顶层步骤摘要（供步骤列表显示）。"""
    rows: List[Dict[str, Any]] = []
    for idx, step in enumerate(steps(flow)):
        stype = str(step.get("type", ""))
        action = step.get("action") or {"power_on": "power.output_on", "power_off": "power.output_off"}.get(stype, "")
        spec = cap.action(action) if action else None
        if spec:
            summary = "%s · %s" % (step.get("instrument", ""), spec.get("label", action))
        elif stype == "measure":
            summary = "%s · %s(%s, CH%s)" % (step.get("instrument", ""), step.get("method", ""),
                                             (step.get("params") or {}).get("item", ""),
                                             (step.get("params") or {}).get("channel", ""))
        elif stype == "wait":
            summary = "等待 %ss" % step.get("seconds", 0)
        elif stype == "compute":
            summary = "%s → %s" % (step.get("algorithm", ""), step.get("output", "result"))
        elif stype == "limit_check":
            summary = "%s ∈ [%s, %s]" % (step.get("variable", ""), step.get("lower", "-∞"), step.get("upper", "+∞"))
        elif stype == "store":
            summary = "记录 %s" % step.get("variable", step.get("name", ""))
        elif stype == "report":
            summary = "填报 %s" % (list((step.get("mapping") or {}).keys()) or "")
        elif stype == "loop":
            summary = "循环 ×%s（含 %d 个子步骤）" % (step.get("count", 1), len(step.get("body", []) or []))
        elif stype == "branch":
            summary = "条件分支"
        else:
            summary = stype
        rows.append({
            "index": idx,
            "seq": idx + 1,
            "stepId": step.get("id", ""),
            "stepType": stype,
            "action": action,
            "instrument": step.get("instrument", ""),
            "summary": summary,
            "editable": stype not in ("loop", "branch"),
        })
    return rows


def addable_actions() -> List[Dict[str, Any]]:
    """可添加的动作/步骤清单（供"添加"下拉框）。"""
    rows = []
    for a in cap.all_actions():
        rows.append({"kind": a["kind"], "id": a["id"], "label": a["capability"] + " · " + a["label"],
                     "action": a["id"], "stepType": "action"})
    for b in BUILTIN_STEPS:
        rows.append({"kind": "builtin", "id": b["type"], "label": "内置 · " + b["label"],
                     "action": "", "stepType": b["type"]})
    return rows


def step_params(step: Dict[str, Any]) -> List[Dict[str, Any]]:
    """返回该步骤的可编辑参数（含当前值），供界面自动生成控件。"""
    stype = str(step.get("type", ""))
    params = dict(step.get("params") or {})
    out: List[Dict[str, Any]] = []

    action = step.get("action") or {"power_on": "power.output_on", "power_off": "power.output_off"}.get(stype, "")
    spec = cap.action(action) if action else None

    if spec:
        for p in spec.get("params", []):
            out.append({
                "name": p["name"], "label": p.get("label", p["name"]), "type": p.get("type", "float"),
                "unit": p.get("unit", ""), "value": params.get(p["name"], p.get("default")),
                "min": p.get("min"), "max": p.get("max"), "options": p.get("options", []),
            })
        return out

    if stype == "measure":
        out.append({"name": "item", "label": "测量项", "type": "str", "unit": "",
                    "value": params.get("item", "vpp"), "options": _MEASURE_ITEMS})
        out.append({"name": "channel", "label": "通道", "type": "int", "unit": "",
                    "value": params.get("channel", 1), "min": 1, "max": 4, "options": []})
        return out

    if stype == "wait":
        out.append({"name": "seconds", "label": "时长", "type": "float", "unit": "s",
                    "value": step.get("seconds", 0), "min": 0, "max": 3600, "options": []})
        return out

    if stype == "compute":
        out.append({"name": "algorithm", "label": "算法", "type": "str", "unit": "",
                    "value": step.get("algorithm", "vpp"),
                    "options": [a["id"] for a in alg.list_algorithms()]})
        out.append({"name": "a", "label": "输入 A", "type": "str", "unit": "",
                    "value": (step.get("inputs") or {}).get("a", ""), "options": []})
        out.append({"name": "b", "label": "输入 B", "type": "str", "unit": "",
                    "value": (step.get("inputs") or {}).get("b", ""), "options": []})
        out.append({"name": "output", "label": "输出变量", "type": "str", "unit": "",
                    "value": step.get("output", "result"), "options": []})
        return out

    if stype == "limit_check":
        out.append({"name": "variable", "label": "变量", "type": "str", "unit": "",
                    "value": step.get("variable", ""), "options": []})
        out.append({"name": "lower", "label": "下限", "type": "float", "unit": "",
                    "value": step.get("lower"), "options": []})
        out.append({"name": "upper", "label": "上限", "type": "float", "unit": "",
                    "value": step.get("upper"), "options": []})
        return out

    if stype == "store":
        out.append({"name": "variable", "label": "变量", "type": "str", "unit": "",
                    "value": step.get("variable", ""), "options": []})
        out.append({"name": "unit", "label": "单位", "type": "str", "unit": "",
                    "value": step.get("unit", ""), "options": []})
        return out

    return out


# ----------------------------------------------------------------------------
# 编辑操作
# ----------------------------------------------------------------------------

def add_step(flow: Dict[str, Any], action_id: str, instrument: str = "") -> int:
    """按能力动作或内置类型追加步骤，返回新步骤索引。"""
    spec = cap.action(action_id)
    if spec:
        params = cap.default_params(action_id)
        iid = instrument or _default_instrument_for(spec)
        step = {
            "id": "step-%d" % (len(steps(flow)) + 1),
            "type": "action",
            "instrument": iid,
            "action": action_id,
            "name": action_id,
            "params": params,
        }
    else:
        step = _builtin_step(action_id, len(steps(flow)) + 1)
    steps(flow).append(step)
    return len(steps(flow)) - 1


def _default_instrument_for(spec: Dict[str, Any]) -> str:
    return {"power": "power1", "scope": "scope1"}.get(spec.get("capability", ""), "")


def _builtin_step(step_type: str, seq: int) -> Dict[str, Any]:
    base = {"id": "step-%d" % seq, "type": step_type}
    if step_type == "wait":
        base["seconds"] = 0.5
    elif step_type == "compute":
        base.update({"algorithm": "vpp", "inputs": {"values": "$wave"}, "output": "result"})
    elif step_type == "limit_check":
        base.update({"variable": "result", "lower": None, "upper": None})
    elif step_type == "store":
        base.update({"variable": "result", "unit": ""})
    elif step_type == "report":
        base.update({"mapping": {"result": "结果"}})
    elif step_type == "loop":
        base.update({"count": 2, "body": []})
    elif step_type == "branch":
        base.update({"condition": {"left": "result", "op": ">", "right": 0},
                     "then": [], "else": []})
    return base


def remove_step(flow: Dict[str, Any], index: int) -> bool:
    items = steps(flow)
    if 0 <= int(index) < len(items):
        items.pop(int(index))
        return True
    return False


def move_step(flow: Dict[str, Any], index: int, delta: int) -> bool:
    items = steps(flow)
    i, j = int(index), int(index) + int(delta)
    if 0 <= i < len(items) and 0 <= j < len(items):
        items[i], items[j] = items[j], items[i]
        return True
    return False


def set_param(flow: Dict[str, Any], index: int, name: str, value: Any) -> bool:
    items = steps(flow)
    if not (0 <= int(index) < len(items)):
        return False
    step = items[int(index)]
    stype = str(step.get("type", ""))
    name = str(name)

    # 简单类型转换
    def conv(v):
        if v is None or v == "":
            return None
        ptype = _PARAM_TYPES.get(name, "str")
        try:
            if ptype == "int":
                return int(float(v))
            if ptype == "float":
                return float(v)
        except (TypeError, ValueError):
            return v
        return str(v)

    if name in ("seconds", "algorithm", "output", "variable", "lower", "upper", "unit"):
        step[name] = conv(value)
        return True
    if name in ("a", "b"):
        step.setdefault("inputs", {})
        step["inputs"][name] = conv(value)
        return True
    step.setdefault("params", {})
    step["params"][name] = conv(value)
    return True

