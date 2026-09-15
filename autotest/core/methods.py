"""测试方法库：把"一类指标怎么测"映射为可执行函数。

原型阶段方法集：
  - identify     读取仪器识别串 *IDN?
  - query        发送任意 SCPI 查询，尝试解析为数字
  - measure_item 示波器自动测量：:MEASure:ITEM? <item>,CHANnel<n>
                 （Rigol DHO900 系；无效值 9.9E+37 自动判为 None）
方法签名统一为： method(instrument, params) -> Measurement
"""
from __future__ import annotations

from typing import Any, Dict

from ..hal.rigol_dho import MEASURE_ITEM_UNITS, parse_measure_value
from .models import Measurement

# 便于流程书写的短名 -> 标准 SCPI item 拼写
ITEM_ALIASES = {
    "vpp": "VPP",
    "vmax": "VMAX",
    "vmin": "VMIN",
    "vrms": "VRMS",
    "vavg": "VAVG",
    "vamp": "VAMP",
    "vtop": "VTOP",
    "vbase": "VBASe",
    "freq": "FREQuency",
    "frequency": "FREQuency",
    "period": "PERiod",
    "per": "PERiod",
    "rtime": "RTIMe",
    "ftime": "FTIMe",
    "pduty": "PDUTy",
    "nduty": "NDUTy",
    "pwidth": "PWIDth",
    "nwidth": "NWIDth",
}


def _normalize_item(item: str) -> str:
    key = str(item).strip().lower()
    return ITEM_ALIASES.get(key, str(item).strip())


def identify(instrument, params: Dict[str, Any]):
    """读取仪器识别串 *IDN?。"""
    raw = instrument.query("*IDN?")
    return Measurement(
        name=params.get("name", "instrument_id"),
        value=None,
        unit="",
        instrument_id=getattr(instrument, "instrument_id", ""),
        raw_value=raw,
    )


def query(instrument, params: Dict[str, Any]):
    """发送一条 SCPI 查询，尝试把返回值解析为数字。"""
    command = params["command"]
    raw = instrument.query(command)
    value = parse_measure_value(raw)

    return Measurement(
        name=params.get("name", command),
        value=value,
        unit=params.get("unit", ""),
        instrument_id=getattr(instrument, "instrument_id", ""),
        raw_value=raw,
    )


def measure_item(instrument, params: Dict[str, Any]):
    """示波器自动测量：:MEASure:ITEM? <item>,CHANnel<n>。

    params:
      item    测量项，支持短名（vpp/vrms/freq/period/rtime/ftime/pduty...）
             或标准拼写（VPP/FREQuency/PERiod/RTIMe...）
      channel 通道号 1..n，默认 1
      name    结果名（默认 "<item>_CH<n>"）
      unit    覆盖自动推导的单位

    无效测量（无信号等，返回约 9.9E+37）时 value=None，原始返回保留在 raw_value。
    """
    item = _normalize_item(params["item"])
    channel = int(params.get("channel", 1))

    # 优先走驱动的示波器语义接口（真机驱动），否则回退到通用 SCPI 查询
    if hasattr(instrument, "measure_item"):
        value, raw = instrument.measure_item(item, channel)
    else:
        raw = instrument.query(":MEASure:ITEM? %s,CHANnel%d" % (item, channel)).strip()
        value = parse_measure_value(raw)

    name = params.get("name") or "%s_CH%d" % (item, channel)
    unit = params.get("unit", "")
    if not unit:
        unit = MEASURE_ITEM_UNITS.get(item, "")
        if not unit and hasattr(instrument, "item_unit"):
            unit = instrument.item_unit(item)

    return Measurement(
        name=name,
        value=value,
        unit=unit,
        instrument_id=getattr(instrument, "instrument_id", ""),
        raw_value=raw,
    )


METHOD_REGISTRY = {
    "identify": identify,
    "query": query,
    "measure_item": measure_item,
}


def get_method(name: str):
    try:
        return METHOD_REGISTRY[name]
    except KeyError:
        raise KeyError("未注册的测试方法: %r，可用方法: %s" % (name, list(METHOD_REGISTRY)))
