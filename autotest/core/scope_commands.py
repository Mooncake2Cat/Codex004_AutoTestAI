"""示波器面板参数 -> SCPI 命令映射（Rigol DHO900 系列 / DHO924S）。

集中的命令拼写表：界面（QML）只改参数，本模块负责生成正确的 SCPI 字符串，
再由控制器下发给真机（type=rigol_dho）。官方编程手册已确认的命令：
  :CHANnel<n>:SCALe / OFFSet / COUPling / BWLimit
  :TIMebase[:MAIN]:SCALe / :TIMebase:MAIN:OFFSet
  :TRIGger:EDGE:SLOPe / LEVel、:TRIGger:SWEep
  :RUN / :STOP / :AUToset / :SYStem:AUToscale / :CLEar
  :MEASure:ITEM、:MEASure:CLEar、:MEASure:STATistic:*、:MEASure:STATistic:DISPlay
  :SOURce:VOLTage:AMPLitude / :SOURce:FREQuency / :SOURce:FUNCtion:RAMP:SYMMetry
未能在手册正文提取到、按 Rigol 标准拼写补齐（同样集中在下方，若真机有差异只改这里）：
  :CHANnel<n>:DISPlay / INVert / PROBe、:TRIGger:EDGE:SOURce、:SOURce:FUNCtion、:SOURce:OUTPut
"""
from __future__ import annotations

from typing import Iterable

MAX_CHANNELS = 4

COUPLINGS = ("DC", "AC", "GND")
SWEEPS = ("AUTO", "NORMal", "SINGle")
SLOPES = ("POSitive", "NEGative", "RFALl")
AFG_FUNCTIONS = ("SINusoid", "SQUare", "RAMP", "PULSe", "DC")

# 短名 -> 官方测量项拼写
MEASURE_ITEMS = {
    "vpp": "VPP",
    "vmax": "VMAX",
    "vmin": "VMIN",
    "vtop": "VTOP",
    "vbase": "VBASe",
    "vavg": "VAVG",
    "vrms": "VRMS",
    "freq": "FREQuency",
    "frequency": "FREQuency",
    "per": "PERiod",
    "period": "PERiod",
    "rtime": "RTIMe",
    "ftime": "FTIMe",
    "pduty": "PDUTy",
    "nduty": "NDUTy",
    "pwidth": "PWIDth",
    "nwidth": "NWIDth",
}


def channel_source(channel: int) -> str:
    ch = int(channel)
    if ch < 1 or ch > MAX_CHANNELS:
        raise ValueError("通道号超出范围 1..%d: %r" % (MAX_CHANNELS, channel))
    return "CHANnel%d" % ch


def _num(value) -> str:
    """数值格式化：优先科学计数，保证仪器可解析。"""
    f = float(value)
    if f == 0:
        return "0"
    return "%.6g" % f


def _onoff(value) -> str:
    return "ON" if bool(value) else "OFF"


# ---------------- 垂直（通道） ----------------

def channel_display(channel: int, on) -> str:
    return ":CHANnel%d:DISPlay %s" % (int(channel), _onoff(on))


def channel_scale(channel: int, volts_per_div: float) -> str:
    v = float(volts_per_div)
    if v <= 0:
        raise ValueError("V/div 必须为正数: %r" % volts_per_div)
    return ":CHANnel%d:SCALe %s" % (int(channel), _num(v))


def channel_offset(channel: int, volts: float) -> str:
    return ":CHANnel%d:OFFSet %s" % (int(channel), _num(volts))


def channel_coupling(channel: int, coupling: str) -> str:
    c = str(coupling).upper()
    if c not in COUPLINGS:
        raise ValueError("耦合方式须为 %s 之一: %r" % (COUPLINGS, coupling))
    return ":CHANnel%d:COUPling %s" % (int(channel), c)


def channel_probe(channel: int, ratio: float) -> str:
    r = float(ratio)
    if r <= 0:
        raise ValueError("探头比必须为正数: %r" % ratio)
    return ":CHANnel%d:PROBe %s" % (int(channel), _num(r))


def channel_bwlimit(channel: int, on) -> str:
    # 官方示例：:CHANnel1:BWLimit 20M
    return ":CHANnel%d:BWLimit %s" % (int(channel), "20M" if bool(on) else "OFF")


def channel_invert(channel: int, on) -> str:
    return ":CHANnel%d:INVert %s" % (int(channel), _onoff(on))


# ---------------- 水平（时基） ----------------

def timebase_scale(seconds_per_div: float) -> str:
    v = float(seconds_per_div)
    if v <= 0:
        raise ValueError("时基必须为正数: %r" % seconds_per_div)
    return ":TIMebase:MAIN:SCALe %s" % _num(v)


def timebase_offset(seconds: float) -> str:
    return ":TIMebase:MAIN:OFFSet %s" % _num(seconds)


# ---------------- 触发 ----------------

def trigger_sweep(mode: str) -> str:
    m = str(mode)
    low = m.lower()
    for cand in SWEEPS:
        if cand.lower() == low or cand.lower().startswith(low):
            return ":TRIGger:SWEep %s" % cand
    raise ValueError("触发模式须为 %s 之一: %r" % (SWEEPS, mode))


def trigger_source(channel: int) -> str:
    return ":TRIGger:EDGE:SOURce %s" % channel_source(channel)


def trigger_slope(slope: str) -> str:
    s = str(slope).lower()
    for cand in SLOPES:
        if cand.lower() == s or cand.lower().startswith(s):
            return ":TRIGger:EDGE:SLOPe %s" % cand
    raise ValueError("触发斜率须为 %s 之一: %r" % (SLOPES, slope))


def trigger_level(volts: float) -> str:
    return ":TRIGger:EDGE:LEVel %s" % _num(volts)


# ---------------- 采集控制 ----------------

def run() -> str:
    return ":RUN"


def stop() -> str:
    return ":STOP"


def single() -> str:
    return ":SINGle"


def force_trigger() -> str:
    return ":TFORce"


def autoset() -> str:
    return ":AUToset"


def clear() -> str:
    return ":CLEar"


# ---------------- 测量 ----------------

def measure_item(item: str, channel: int) -> str:
    key = str(item).strip().lower()
    canonical = MEASURE_ITEMS.get(key, str(item).strip())
    return ":MEASure:ITEM %s,%s" % (canonical, channel_source(channel))


def measure_item_query(item: str, channel: int) -> str:
    """查询型：:MEASure:ITEM? <item>,<source>（只读，用于界面轮询真机读数）。"""
    key = str(item).strip().lower()
    canonical = MEASURE_ITEMS.get(key, str(item).strip())
    return ":MEASure:ITEM? %s,%s" % (canonical, channel_source(channel))


def measure_clear() -> str:
    return ":MEASure:CLEar"


def measure_stat_display(on) -> str:
    return ":MEASure:STATistic:DISPlay %s" % _onoff(on)


def measure_stat_reset() -> str:
    return ":MEASure:STATistic:RESet"


# ---------------- 内置信号源（AFG，DHO924S 有） ----------------

# 常见别名 -> 官方波形名
_AFG_ALIASES = {
    "sin": "SINusoid", "sine": "SINusoid", "sinewave": "SINusoid",
    "squ": "SQUare", "square": "SQUare",
    "ramp": "RAMP", "pulse": "PULSe", "dc": "DC",
}


def afg_function(name: str) -> str:
    n = str(name).lower().strip()
    if n in _AFG_ALIASES:
        return ":SOURce:FUNCtion %s" % _AFG_ALIASES[n]
    for cand in AFG_FUNCTIONS:
        if cand.lower() == n or cand.lower().startswith(n) or n.startswith(cand.lower()):
            return ":SOURce:FUNCtion %s" % cand
    raise ValueError("波形须为 %s 之一: %r" % (AFG_FUNCTIONS, name))


def afg_frequency(hz: float) -> str:
    return ":SOURce:FREQuency %s" % _num(hz)


def afg_amplitude(vpp: float) -> str:
    return ":SOURce:VOLTage:AMPLitude %s" % _num(vpp)


def afg_offset(volts: float) -> str:
    return ":SOURce:VOLTage:OFFSet %s" % _num(volts)


def afg_output(on) -> str:
    # 官方手册 3.25.1：:SOURce:OUTPut:STATe（注意有 :STATe，缺了会报 -100 Command error）
    return ":SOURce:OUTPut:STATe %s" % _onoff(on)


def measure_items() -> Iterable[str]:
    return tuple(MEASURE_ITEMS)



