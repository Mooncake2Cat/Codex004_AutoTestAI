"""鼎阳 SPD3303X-E 可编程直流电源驱动（LAN SCPI）。

命令按 SPD 系列常见 SCPI 编写，**待真机核对**；拼写集中在下方常量，便于修正：
    *IDN?                          识别
    :CHANnel<n>:VOLTage <v>        设定电压
    :CHANnel<n>:VOLTage?           查询设定电压
    :CHANnel<n>:CURRent <a>        设定电流
    :CHANnel<n>:CURRent?           查询设定电流
    :CHANnel<n>:OUTPut ON|OFF      输出开关
    :CHANnel<n>:OUTPut?            查询输出状态
    :MEASure:VOLTage? CHANnel<n>   实测电压
    :MEASure:CURRent? CHANnel<n>   实测电流
"""
from __future__ import annotations

from typing import Optional

from ..scpi import TcpScpiInstrument

CMD_VOLT_SET = ":CHANnel%d:VOLTage %.4f"
CMD_VOLT_GET = ":CHANnel%d:VOLTage?"
CMD_CURR_SET = ":CHANnel%d:CURRent %.4f"
CMD_CURR_GET = ":CHANnel%d:CURRent?"
CMD_OUT_SET = ":CHANnel%d:OUTPut %s"
CMD_OUT_GET = ":CHANnel%d:OUTPut?"
CMD_MEAS_VOLT = ":MEASure:VOLTage? CHANnel%d"
CMD_MEAS_CURR = ":MEASure:CURRent? CHANnel%d"


def _to_float(text: str) -> Optional[float]:
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return None


class SiglentSpdInstrument(TcpScpiInstrument):
    """SPD3303X-E（三路可编程直流电源），默认 LAN SCPI 端口 5025。"""

    def __init__(
        self,
        host: str,
        port: int = 5025,
        timeout: float = 3.0,
        terminator: str = "\n",
        channels: int = 3,
        model: str = "SPD3303X-E",
    ):
        super().__init__(host=host, port=port, timeout=timeout, terminator=terminator)
        self.model = model
        self.channels = int(channels)
        self._instrument_id = "siglent_spd:%s:%s" % (host, self.port)

    def _check_channel(self, channel: int) -> int:
        ch = int(channel)
        if ch < 1 or ch > self.channels:
            raise ValueError("通道号超出范围 1..%d: %r" % (self.channels, channel))
        return ch

    # ---------- 设定 ----------
    def set_voltage(self, channel: int, volts: float) -> None:
        self.write(CMD_VOLT_SET % (self._check_channel(channel), float(volts)))

    def set_current(self, channel: int, amps: float) -> None:
        self.write(CMD_CURR_SET % (self._check_channel(channel), float(amps)))

    def set_output(self, channel: int, on: bool) -> None:
        self.write(CMD_OUT_SET % (self._check_channel(channel), "ON" if on else "OFF"))

    # ---------- 查询 ----------
    def get_voltage(self, channel: int) -> Optional[float]:
        return _to_float(self.query(CMD_VOLT_GET % self._check_channel(channel)))

    def get_current(self, channel: int) -> Optional[float]:
        return _to_float(self.query(CMD_CURR_GET % self._check_channel(channel)))

    def get_output(self, channel: int) -> Optional[bool]:
        resp = self.query(CMD_OUT_GET % self._check_channel(channel)).strip().upper()
        if resp.startswith("ON") or resp in ("1", "ON,1"):
            return True
        if resp.startswith("OFF") or resp in ("0", "OFF,0"):
            return False
        return None

    def measure_voltage(self, channel: int) -> Optional[float]:
        return _to_float(self.query(CMD_MEAS_VOLT % self._check_channel(channel)))

    def measure_current(self, channel: int) -> Optional[float]:
        return _to_float(self.query(CMD_MEAS_CURR % self._check_channel(channel)))
