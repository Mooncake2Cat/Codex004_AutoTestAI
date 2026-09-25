"""统一能力模型（Capability Model）：仪器"能做什么"的声明 + 执行。

设计（设计文档 §8）：
  - 能力动作（action）：声明式描述，供**流程编辑器自动生成控件**、**引擎执行**、**架构台展示**；
  - 混合模式：常规操作走能力动作；冷门功能保留"原生命令"逃生口（raw 动作）；
  - 安全动作（safe_action）：流程"停止"时自动回安全态（电源断电、示波器停止采集）。

动作描述字段：
    id          动作标识，如 "power.set_voltage"
    capability  能力名（power / scope / voltmeter ...）
    label       中文名（界面显示）
    device_types 适用的仪器类型
    params      参数列表 [{name,label,type,unit,min,max,default,options}]
    kind        "action"（设置类）/ "measure"（读取类）
    result      measure 类的结果描述 {name,unit}
    safe        是否可作为安全动作
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..bus.event_bus import bus
from . import scope_commands as sc

# ----------------------------------------------------------------------------
# 动作声明
# ----------------------------------------------------------------------------

def _p(name, label, ptype="float", unit="", **kw):
    d = {"name": name, "label": label, "type": ptype, "unit": unit}
    d.update(kw)
    return d


ACTIONS: List[Dict[str, Any]] = [
    # ---------- 电源（鼎阳 SPD3303X-E / 虚拟电源） ----------
    {
        "id": "power.output_on", "capability": "power", "label": "输出开",
        "device_types": ["siglent_spd3303x"], "kind": "action", "safe": False,
        "params": [_p("channel", "通道", "int", min=1, max=3, default=1)],
    },
    {
        "id": "power.output_off", "capability": "power", "label": "输出关",
        "device_types": ["siglent_spd3303x"], "kind": "action", "safe": True,
        "params": [_p("channel", "通道", "int", min=1, max=3, default=1)],
    },
    {
        "id": "power.set_voltage", "capability": "power", "label": "设置电压",
        "device_types": ["siglent_spd3303x"], "kind": "action", "safe": False,
        "params": [
            _p("channel", "通道", "int", min=1, max=3, default=1),
            _p("volts", "电压", "float", "V", min=0, max=32, default=5.0),
        ],
    },
    {
        "id": "power.set_current", "capability": "power", "label": "设置电流",
        "device_types": ["siglent_spd3303x"], "kind": "action", "safe": False,
        "params": [
            _p("channel", "通道", "int", min=1, max=3, default=1),
            _p("amps", "电流", "float", "A", min=0, max=3.2, default=1.0),
        ],
    },
    {
        "id": "power.measure_voltage", "capability": "power", "label": "读电压",
        "device_types": ["siglent_spd3303x"], "kind": "measure", "safe": False,
        "params": [_p("channel", "通道", "int", min=1, max=3, default=1)],
        "result": {"name": "voltage", "unit": "V"},
    },
    {
        "id": "power.measure_current", "capability": "power", "label": "读电流",
        "device_types": ["siglent_spd3303x"], "kind": "measure", "safe": False,
        "params": [_p("channel", "通道", "int", min=1, max=3, default=1)],
        "result": {"name": "current", "unit": "A"},
    },
    # ---------- 示波器（Rigol DHO900 系列） ----------
    {
        "id": "scope.run", "capability": "scope", "label": "运行(RUN)",
        "device_types": ["rigol_dho"], "kind": "action", "safe": False, "params": [],
    },
    {
        "id": "scope.stop", "capability": "scope", "label": "停止采集(STOP)",
        "device_types": ["rigol_dho"], "kind": "action", "safe": True, "params": [],
    },
    {
        "id": "scope.autoset", "capability": "scope", "label": "自动设置(AUTO)",
        "device_types": ["rigol_dho"], "kind": "action", "safe": False, "params": [],
    },
    {
        "id": "scope.set_timebase", "capability": "scope", "label": "设置时基",
        "device_types": ["rigol_dho"], "kind": "action", "safe": False,
        "params": [_p("seconds_per_div", "时基", "float", "s/div", min=5e-9, max=1, default=2e-4)],
    },
    {
        "id": "scope.set_channel_scale", "capability": "scope", "label": "设置垂直档位",
        "device_types": ["rigol_dho"], "kind": "action", "safe": False,
        "params": [
            _p("channel", "通道", "int", min=1, max=4, default=1),
            _p("volts_per_div", "档位", "float", "V/div", min=0.001, max=10, default=1.0),
        ],
    },
    {
        "id": "scope.measure", "capability": "scope", "label": "自动测量",
        "device_types": ["rigol_dho"], "kind": "measure", "safe": False,
        "params": [
            _p("item", "测量项", "str", default="vpp",
               options=["vpp", "vrms", "vavg", "vmax", "vmin", "freq", "per", "rtime", "ftime", "pduty"]),
            _p("channel", "通道", "int", min=1, max=4, default=1),
        ],
        "result": {"name": "measure", "unit": ""},
    },
]

_ACTION_BY_ID = {a["id"]: a for a in ACTIONS}


# ----------------------------------------------------------------------------
# 查询接口（供界面/引擎使用）
# ----------------------------------------------------------------------------

def all_actions() -> List[Dict[str, Any]]:
    return [dict(a) for a in ACTIONS]


def action(action_id: str) -> Optional[Dict[str, Any]]:
    a = _ACTION_BY_ID.get(str(action_id))
    return dict(a) if a else None


def actions_for_device_type(device_type: str) -> List[Dict[str, Any]]:
    return [dict(a) for a in ACTIONS if device_type in a.get("device_types", [])]


def safe_actions(device_type: str) -> List[Dict[str, Any]]:
    return [dict(a) for a in ACTIONS
            if device_type in a.get("device_types", []) and a.get("safe")]


def default_params(action_id: str) -> Dict[str, Any]:
    a = action(action_id)
    if not a:
        return {}
    return {p["name"]: p.get("default") for p in a.get("params", [])}


# ----------------------------------------------------------------------------
# 执行
# ----------------------------------------------------------------------------

def execute(instrument, action_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """在指定仪器上执行能力动作。

    返回 {"ok": bool, "value": Any, "unit": str, "detail": str}
    """
    params = dict(params or {})
    a = action(action_id)
    if a is None:
        return {"ok": False, "value": None, "unit": "", "detail": "未知能力动作: %s" % action_id}
    try:
        return _execute(instrument, action_id, params)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "value": None, "unit": "", "detail": "%s: %s" % (type(exc).__name__, exc)}


def _execute(instrument, action_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    from ..hal.devices import power_siglent as pw

    def num(key, default=0.0):
        try:
            return float(params.get(key, default))
        except (TypeError, ValueError):
            return float(default)

    def integer(key, default=1):
        try:
            return int(float(params.get(key, default)))
        except (TypeError, ValueError):
            return int(default)

    # ---------- 电源 ----------
    if action_id == "power.output_on":
        ch = integer("channel")
        instrument.write(pw.CMD_OUT_SET % (ch, "ON"))
        return {"ok": True, "value": True, "unit": "", "detail": "CH%d 输出 ON" % ch}
    if action_id == "power.output_off":
        ch = integer("channel")
        instrument.write(pw.CMD_OUT_SET % (ch, "OFF"))
        return {"ok": True, "value": False, "unit": "", "detail": "CH%d 输出 OFF" % ch}
    if action_id == "power.set_voltage":
        ch, v = integer("channel"), num("volts")
        instrument.write(pw.CMD_VOLT_SET % (ch, v))
        return {"ok": True, "value": v, "unit": "V", "detail": "CH%d 电压 %.4f V" % (ch, v)}
    if action_id == "power.set_current":
        ch, a = integer("channel"), num("amps")
        instrument.write(pw.CMD_CURR_SET % (ch, a))
        return {"ok": True, "value": a, "unit": "A", "detail": "CH%d 电流 %.4f A" % (ch, a)}
    if action_id == "power.measure_voltage":
        ch = integer("channel")
        raw = instrument.query(pw.CMD_MEAS_VOLT % ch)
        return {"ok": True, "value": _f(raw), "unit": "V", "detail": "CH%d 实测电压 %s" % (ch, raw.strip())}
    if action_id == "power.measure_current":
        ch = integer("channel")
        raw = instrument.query(pw.CMD_MEAS_CURR % ch)
        return {"ok": True, "value": _f(raw), "unit": "A", "detail": "CH%d 实测电流 %s" % (ch, raw.strip())}

    # ---------- 示波器 ----------
    if action_id == "scope.run":
        instrument.write(sc.run())
        return {"ok": True, "value": None, "unit": "", "detail": "RUN"}
    if action_id == "scope.stop":
        instrument.write(sc.stop())
        return {"ok": True, "value": None, "unit": "", "detail": "STOP"}
    if action_id == "scope.autoset":
        instrument.write(sc.autoset())
        return {"ok": True, "value": None, "unit": "", "detail": "AUTO"}
    if action_id == "scope.set_timebase":
        instrument.write(sc.timebase_scale(num("seconds_per_div", 2e-4)))
        return {"ok": True, "value": num("seconds_per_div", 2e-4), "unit": "s/div", "detail": "时基已设置"}
    if action_id == "scope.set_channel_scale":
        ch = integer("channel")
        instrument.write(sc.channel_scale(ch, num("volts_per_div", 1.0)))
        return {"ok": True, "value": num("volts_per_div", 1.0), "unit": "V/div", "detail": "CH%d 档位已设置" % ch}
    if action_id == "scope.measure":
        item = str(params.get("item", "vpp"))
        ch = integer("channel")
        cmd = sc.measure_item_query(item, ch)
        raw = instrument.query(cmd)
        from ..hal.rigol_dho import parse_measure_value
        value = parse_measure_value(raw)
        unit = {"vpp": "V", "vrms": "V", "vavg": "V", "vmax": "V", "vmin": "V",
                "freq": "Hz", "per": "s", "rtime": "s", "ftime": "s", "pduty": "%"}.get(item.lower(), "")
        return {"ok": value is not None, "value": value, "unit": unit,
                "detail": "%s,CH%d = %s" % (item, ch, raw.strip())}

    return {"ok": False, "value": None, "unit": "", "detail": "动作未实现: %s" % action_id}


def _f(text: Any) -> Optional[float]:
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return None


def restore_safe_state(instruments: Dict[str, Any], defs: List[Dict[str, Any]]) -> List[str]:
    """流程停止时调用：对每台仪器执行其安全动作（如电源断电、示波器 STOP）。"""
    done: List[str] = []
    for cfg in defs:
        iid = cfg.get("id")
        inst = instruments.get(iid)
        if inst is None:
            continue
        for act in safe_actions(cfg.get("type", "")):
            params = default_params(act["id"])
            # 电源：关闭所有通道
            if act["id"] == "power.output_off":
                channels = (cfg.get("options") or {}).get("channels", 3)
                for ch in range(1, int(channels) + 1):
                    p = dict(params)
                    p["channel"] = ch
                    r = execute(inst, act["id"], p)
                    done.append("%s %s -> %s" % (iid, act["id"], r.get("detail", "")))
            else:
                r = execute(inst, act["id"], params)
                done.append("%s %s -> %s" % (iid, act["id"], r.get("detail", "")))
    bus.publish("app", "safe", "restoreSafeState", detail="; ".join(done)[:180], result="%d 个动作" % len(done))
    return done
