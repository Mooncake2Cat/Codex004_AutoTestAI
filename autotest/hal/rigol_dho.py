"""Rigol DHO900 系列（含 DHO924S）网口示波器驱动。

通讯方式（经官方 DHO900 编程手册与多个已真机验证的开源实现交叉确认）：
  - LAN raw SCPI socket：TCP 端口 5555（Rigol 示波器非标准端口，非 5025）
  - 命令以换行符分隔；查询返回以换行结尾
  - 自动测量命令族：:MEASure:ITEM <item>[,<src>]
    查询示例：:MEASure:ITEM? VPP,CHANnel1
  - 无有效信号时测量值返回约 9.9E+37，本驱动将其判定为“无效/测不出”

说明：端口、超时、换行符均做成可配置项，若真机行为与默认有差异，
只需修改 config 而无需改代码；scripts/dho_selftest.py 可一键对真机核验。
"""
from __future__ import annotations

import math
import re
from typing import Optional, Tuple

from .scpi import TcpScpiInstrument

# Rigol 无效测量哨兵值（约 9.9e37；不同型号也可能为 9.9e36），凡绝对值 >= 1e36 视为无效
_INVALID_THRESHOLD = 1e36

# DHO900 常用自动测量项 -> 单位（供方法层/界面显示，可按 params 覆盖）
MEASURE_ITEM_UNITS = {
    "VMAX": "V",
    "VMIN": "V",
    "VPP": "V",
    "VTOP": "V",
    "VBASe": "V",
    "VAMP": "V",
    "VAVG": "V",
    "VRMS": "V",
    "PVRMS": "V",
    "FREQuency": "Hz",
    "PERiod": "s",
    "PWIDth": "s",
    "NWIDth": "s",
    "PDUTy": "%",
    "NDUTy": "%",
    "RTIMe": "s",
    "FTIMe": "s",
    "OVERshoot": "%",
    "PREshoot": "%",
    "TVMAX": "s",
    "TVMIN": "s",
}

_ITEM_RE = re.compile(r"^[A-Za-z]+$")
_CHAN_RE = re.compile(r"^CHANnel([1-9][0-9]*)$", re.IGNORECASE)


def parse_preamble(text: str) -> dict:
    """解析 :WAVeform:PREamble? 的返回值（10 个逗号分隔字段）。

    顺序（Rigol DHO800/900 编程手册 3.28.14）：
      format, type, points, count, xincrement, xorigin, xreference,
      yincrement, yorigin, yreference
    """
    parts = [p.strip() for p in str(text).replace("\n", "").split(",")]
    if len(parts) < 10:
        raise ValueError("Preamble 字段不足 10 个: %r" % text)
    keys = [
        "format", "type", "points", "count",
        "xincrement", "xorigin", "xreference",
        "yincrement", "yorigin", "yreference",
    ]
    out = {}
    for key, raw in zip(keys, parts):
        try:
            out[key] = float(raw)
        except (TypeError, ValueError):
            out[key] = raw
    return out


def convert_waveform(payload: bytes, preamble: dict) -> list:
    """把 :WAVeform:DATA? 的原始采样换算为电压。

    公式（手册/NORMal 模式）：V = (raw − YORigin − YREFerence) × YINCrement
    payload 的编码由 preamble['format'] 决定：0=BYTE(1 字节)、1=WORD(2 字节)。
    """
    import struct

    yinc = float(preamble["yincrement"])
    yorigin = float(preamble["yorigin"])
    yref = float(preamble["yreference"])

    fmt = preamble.get("format", 0)
    try:
        fmt_num = int(float(fmt))
    except (TypeError, ValueError):
        fmt_num = 0

    if fmt_num == 1:  # WORD：小端有符号 16 位
        count = len(payload) // 2
        samples = list(struct.unpack("<%dh" % count, payload[: count * 2])) if count else []
    else:             # BYTE：无符号 8 位
        samples = list(payload)

    return [(s - yorigin - yref) * yinc for s in samples]


def parse_measure_value(raw: str) -> Optional[float]:
    """把 DHO 自动测量查询返回解析为 float；无效/不可解析返回 None。

    Rigol 在“当前信号测不出该参数”时返回约 9.9E+37（或 9.9E+36），
    这类值与 nan/inf 一律视为无效，避免污染测量数据。
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    # 去掉可能的单位后缀/多余空白（如 "1.000000E+03" 直接可解析，此分支为兜底）
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    if abs(value) >= _INVALID_THRESHOLD:
        return None
    return value


class RigolDhoInstrument(TcpScpiInstrument):
    """DHO900 系列网口示波器（默认面向 DHO924S）。

    继承通用 TCP SCPI 驱动（socket 连接/读写），在其之上补充示波器语义：
      - measure_item(item, channel)：一次自动测量查询
      - 无效测量值（9.9E+37 等）过滤
    """

    def __init__(
        self,
        host: str,
        port: int = 5555,
        timeout: float = 3.0,
        terminator: str = "\n",
        channels: int = 4,
        model: str = "DHO924S",
    ):
        super().__init__(host=host, port=port, timeout=timeout, terminator=terminator)
        self.model = model
        self.channels = int(channels)
        self._instrument_id = "rigol_dho:%s:%s" % (host, self.port)

    # ---------- 示波器语义 ----------
    def channel_name(self, channel: int) -> str:
        """把 1..n 通道号映射为 SCPI 源名 CHANnel<n>。"""
        channel = int(channel)
        if channel < 1 or channel > self.channels:
            raise ValueError("通道号超出范围 1..%d: %r" % (self.channels, channel))
        return "CHANnel%d" % channel

    def measure_item(self, item: str, channel: int = 1, timeout: Optional[float] = None) -> Tuple[Optional[float], str]:
        """查询 :MEASure:ITEM? <item>,<source>，返回 (value, raw)。

        value 为 None 表示无效/测不出（例如无信号时返回 9.9E+37）。
        """
        item = str(item).strip()
        if not _ITEM_RE.match(item):
            raise ValueError("非法的测量项名称: %r" % item)
        source = self.channel_name(channel)
        raw = self.query(":MEASure:ITEM? %s,%s" % (item, source), timeout=timeout).strip()
        return parse_measure_value(raw), raw

    def item_unit(self, item: str) -> str:
        return MEASURE_ITEM_UNITS.get(str(item).strip(), "")

    # ---------- 波形数据（:WAVeform 族，手册 3.28） ----------
    def read_waveform(self, channel: int = 1, mode: str = "NORMal", fmt: str = "BYTE") -> list:
        """读取指定通道的屏幕波形并换算为电压列表（V）。

        使用 NORMal 模式（屏幕数据，约 1000 点）+ BYTE 格式；
        先读 :WAVeform:PREamble? 拿到换算系数，再读 :WAVeform:DATA? 的二进制块。
        """
        source = self.channel_name(channel)
        self.write(":WAVeform:SOURce %s" % source)
        self.write(":WAVeform:MODE %s" % mode)
        self.write(":WAVeform:FORMat %s" % fmt)
        preamble = parse_preamble(self.query(":WAVeform:PREamble?").strip())
        payload = self.query_binary(":WAVeform:DATA?")
        return convert_waveform(payload, preamble)

