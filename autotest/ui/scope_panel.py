"""示波器操作面板模型（胶合层 QML<->Python 桥接）。

本版本**不含任何仿真波形**：
  - 波形区为空（真机波形下载 :WAVeform 待接入）；
  - 右侧“自动测量”数值来自真机轮询 :MEASure:ITEM?（经控制器下发）；
  - 面板设置（通道/时基/触发/采集/测量/信号源）原样生成 SCPI 下发真机。

职责分工：
  - 本模块：保存面板设置、按设置生成 SCPI、轮询真机测量值、驱动 QML；
  - TestController：真正把命令/查询通过 HAL 发给示波器（mock 模式下只回显）。
"""
from __future__ import annotations

import math

from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, QTimer, Property, Signal, Slot

from ..core import scope_commands as sc
from ..hal.rigol_dho import parse_measure_value

_POLL_INTERVAL_MS = 1000  # 真机测量轮询周期（1 秒）
_WAVE_INTERVAL_MS = 500   # 真机波形刷新周期（约 2 帧/秒，多通道同时抓取）
_SIM_FPS = 25             # 仿真波形帧率（无真机时的软件调试用）
_SIM_DT = 1.0 / _SIM_FPS
_SIM_POINTS = 601         # 仿真采样点数（覆盖 10 格水平宽度）

# 各通道仿真信号定义（信号本身的频率/幅度）；其他显示参数由面板设置决定
_SIGNALS = {
    1: {"wave": "sine", "freq": 1000.0, "amp": 1.65},
    2: {"wave": "square", "freq": 5000.0, "amp": 2.5},
    3: {"wave": "sine", "freq": 20000.0, "amp": 0.5},
    4: {"wave": "square", "freq": 1000.0, "amp": 0.5},
}

_COLORS = {1: "#ffd800", 2: "#00d7ff", 3: "#ff6ec7", 4: "#00d24a"}

_MEASURE_LABELS = [
    ("vpp", "Vpp"), ("vrms", "Vrms"), ("vavg", "Vavg"),
    ("freq", "Freq"), ("per", "Period"), ("rtime", "Rise"),
    ("ftime", "Fall"), ("duty", "Duty"),
]


def _fmt_seconds(value: float) -> str:
    if value == 0:
        return "0 s"
    if abs(value) >= 1.0:
        return "%.3f s" % value
    if abs(value) >= 1e-3:
        return "%.3f ms" % (value * 1e3)
    if abs(value) >= 1e-6:
        return "%.3f µs" % (value * 1e6)
    return "%.3f ns" % (value * 1e9)


def _fmt_volts(value: float) -> str:
    if abs(value) >= 1.0:
        return "%.2f V" % value
    if abs(value) >= 1e-3:
        return "%.0f mV" % (value * 1e3)
    return "%.2f V" % value


def _fmt_freq(value: float) -> str:
    if value >= 1e6:
        return "%.3f MHz" % (value / 1e6)
    if value >= 1e3:
        return "%.3f kHz" % (value / 1e3)
    return "%.3f Hz" % value


class ScopePanel(QObject):
    """示波器面板模型（设置 + 真机测量轮询 + SCPI 下发）。"""

    channelsChanged = Signal()
    runningChanged = Signal()
    stateChanged = Signal()
    commandChanged = Signal()
    measurementsChanged = Signal()
    frameReady = Signal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._running = True

        self._ch: Dict[int, Dict] = {
            ch: {
                "enabled": ch in (1, 2),
                "scale": 1.0 if ch == 1 else 0.5,
                "offset": 0.0,
                "coupling": "DC",
                "probe": 1.0,
                "bwlimit": False,
                "invert": False,
            }
            for ch in (1, 2, 3, 4)
        }
        self._time_scale = 200e-6
        self._time_offset = 0.0
        self._trigger = {"sweep": "AUTO", "source": 1, "slope": "POSitive", "level": 0.0}
        self._measure_items = {k: (k in ("vpp", "vrms", "freq")) for k, _ in _MEASURE_LABELS}
        self._measure_stat = False
        self._afg = {"function": "SINusoid", "freq": 1000.0, "amp": 1.0, "offset": 0.0, "output": False}

        # 真机读数缓存：(channel, item) -> (value|None, raw)
        self._readouts: Dict[Tuple[int, str], Tuple[Optional[float], str]] = {}
        self._state_seq = 0
        self._measure_seq = 0
        self._poll_channel = 1

        self._sink: Optional[Callable[[str], str]] = None
        self._measure_sink: Optional[Callable[[str, int], str]] = None
        self._command_text = ""
        self._command_state = ""

        # 真机波形（默认关闭，避免影响用户在示波器上单独测试）
        self._waveform_on = False
        self._wave_samples: Dict[int, List[float]] = {}
        self._wave_sink: Optional[Callable[[int], list]] = None

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(_POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll)

        self._wave_timer = QTimer(self)
        self._wave_timer.setInterval(_WAVE_INTERVAL_MS)
        self._wave_timer.timeout.connect(self._poll_wave)

        # 仿真模式（无真机时的软件调试）：默认开启，用生成的波形替代真机波形
        self._sim_mode = True
        self._sim_on = True
        self._sim_t = 0.0
        self._sim_tick_count = 0
        self._sim_samples: Dict[int, List[float]] = {}
        self._sim_timer = QTimer(self)
        self._sim_timer.setInterval(int(1000.0 / _SIM_FPS))
        self._sim_timer.timeout.connect(self._tick_sim)

    # ---------- 生命周期 / 注入 ----------
    def start(self) -> None:
        if self._sim_mode:
            if not self._sim_timer.isActive():
                self._sim_timer.start()
        elif not self._poll_timer.isActive():
            self._poll_timer.start()

    def stop(self) -> None:
        self._poll_timer.stop()
        self._wave_timer.stop()
        self._sim_timer.stop()

    def setCommandSink(self, sink: Callable[[str], str]) -> None:
        """控制器注入：把 SCPI 命令下发到真机并返回状态文本。"""
        self._sink = sink

    def setMeasureSink(self, sink: Callable[[str, int], str]) -> None:
        """控制器注入：按 (测量项, 通道) 查询真机测量值，返回原始字符串。"""
        self._measure_sink = sink

    def setWaveformSink(self, sink: Callable[[int], list]) -> None:
        """控制器注入：读取指定通道的真机波形（电压数组）。"""
        self._wave_sink = sink

    @Slot(bool)
    def setSimulationMode(self, on: bool) -> None:
        """切换数据源：True=仿真波形（无真机时的软件调试），False=真机波形/读数。"""
        self._sim_mode = bool(on)
        self._poll_timer.stop()
        self._wave_timer.stop()
        self._sim_timer.stop()
        if self._sim_mode:
            self._sim_on = True
            self._sim_timer.start()
            self._tick_sim()
        else:
            self._sim_samples = {}
            self._poll_timer.start()
            if self._waveform_on:
                self._wave_timer.start()
        self._touch()
        self.frameReady.emit()

    @Slot(bool)
    def setWaveformOn(self, on: bool) -> None:
        """波形显示开关：仿真模式下开关仿真波形；真机模式下开关 :WAVeform 读取。"""
        on = bool(on)
        if self._sim_mode:
            self._sim_on = on
            if on:
                self._sim_timer.start()
                self._tick_sim()
            else:
                self._sim_timer.stop()
                self._sim_samples = {}
        else:
            self._waveform_on = on
            if on:
                self._wave_timer.start()
                self._poll_wave()
            else:
                self._wave_timer.stop()
                self._wave_samples = {}
        self._touch()
        self.frameReady.emit()

    # ---------- 仿真波形（无真机时的软件调试） ----------
    @staticmethod
    def _wave(kind: str, phase: float) -> float:
        if kind == "square":
            return 1.0 if math.sin(phase) >= 0 else -1.0
        if kind == "ramp":
            return 2.0 * (((phase / (2.0 * math.pi)) % 1.0) - 0.5)
        if kind == "dc":
            return 0.0
        return math.sin(phase)

    def _tick_sim(self) -> None:
        """按面板设置（V/div、耦合、反相、时基、AFG）生成所有已开启通道的仿真波形。"""
        if not self._sim_mode or not self._sim_on:
            return
        self._sim_t += _SIM_DT
        window = self._time_scale * 10.0
        out: Dict[int, List[float]] = {}
        for ch in self._enabled_channels():
            info = self._ch[ch]
            sig = dict(_SIGNALS.get(ch, {"wave": "sine", "freq": 1000.0, "amp": 1.0}))
            amp = float(sig["amp"])
            ys: List[float] = []
            for i in range(_SIM_POINTS):
                t = self._time_offset + self._sim_t - window + window * i / (_SIM_POINTS - 1)
                phase = 2.0 * math.pi * float(sig["freq"]) * t
                y = amp * self._wave(str(sig["wave"]), phase)
                if info["invert"]:
                    y = -y
                if info["coupling"] == "GND":
                    y = 0.0
                y += info["offset"]
                ys.append(y)
            out[ch] = ys
        self._sim_samples = out
        # 读数不必每帧刷新（25fps），约 5Hz 更新即可
        self._sim_tick_count += 1
        if self._sim_tick_count % 5 == 0:
            self._update_sim_readouts()
        self.frameReady.emit()

    def _update_sim_readouts(self) -> None:
        """仿真模式下由仿真采样算出读数（不查真机，界面仍有数值可调）。"""
        for ch in self._enabled_channels():
            ys = self._sim_samples.get(ch, [])
            if not ys:
                continue
            sig = _SIGNALS.get(ch, {"freq": 0.0})
            vmax, vmin = max(ys), min(ys)
            freq = float(sig.get("freq", 0.0)) or 0.0
            vals = {
                "vpp": vmax - vmin,
                "vrms": math.sqrt(sum(y * y for y in ys) / len(ys)),
                "vavg": sum(ys) / len(ys),
                "freq": freq,
                "per": (1.0 / freq) if freq else 0.0,
                "rtime": self._edge_time(ys, True),
                "ftime": self._edge_time(ys, False),
                "duty": self._duty(ys),
            }
            for item in self._measure_items:
                self._readouts[(ch, item)] = (vals.get(item, 0.0), "")
        self._measure_seq += 1
        self.measurementsChanged.emit()

    def _edge_time(self, ys: List[float], rising: bool) -> float:
        """估算 10%~90% 上升/下降时间（秒）。"""
        if len(ys) < 2:
            return 0.0
        vmax, vmin = max(ys), min(ys)
        if vmax - vmin <= 1e-12:
            return 0.0
        lo = vmin + 0.1 * (vmax - vmin)
        hi = vmin + 0.9 * (vmax - vmin)
        dt = (self._time_scale * 10.0) / max(len(ys) - 1, 1)
        i_lo = i_hi = None
        for i in range(1, len(ys)):
            a, b = ys[i - 1], ys[i]
            if rising:
                if i_lo is None and a <= lo <= b:
                    i_lo = i
                if i_lo is not None and a <= hi <= b:
                    i_hi = i
                    break
            else:
                if i_lo is None and a >= hi >= b:
                    i_lo = i
                if i_lo is not None and a >= lo >= b:
                    i_hi = i
                    break
        if i_lo is None or i_hi is None:
            return 0.0
        return abs(i_hi - i_lo) * dt

    @staticmethod
    def _duty(ys: List[float]) -> float:
        if not ys:
            return 0.0
        mid = (max(ys) + min(ys)) / 2.0
        return 100.0 * sum(1 for y in ys if y > mid) / len(ys)

    def _poll_wave(self) -> None:
        """抓取**所有已开启通道**的波形，同屏叠加显示（与真实示波器一致）。"""
        if not self._waveform_on or not callable(self._wave_sink):
            return
        samples_map: Dict[int, List[float]] = {}
        for ch in self._enabled_channels():
            try:
                samples = self._wave_sink(ch)
            except Exception:  # noqa: BLE001
                samples = None
            if samples:
                samples_map[ch] = list(samples)
        self._wave_samples = samples_map
        self.frameReady.emit()

    def _touch(self) -> None:
        self._state_seq += 1
        self.stateChanged.emit()

    def _apply(self, command: str) -> None:
        self._command_text = command
        state = "（未配置真机：config 为 mock，命令未下发）"
        if callable(self._sink):
            try:
                state = self._sink(command) or ""
            except Exception as exc:  # noqa: BLE001
                state = "下发异常: %s" % exc
        self._command_state = state
        self.commandChanged.emit()

    # ---------- 真机测量轮询 ----------
    def _enabled_channels(self) -> List[int]:
        """当前已开启显示的通道列表（波形与读数都按它抓取）。"""
        return [ch for ch in (1, 2, 3, 4) if self._ch.get(ch, {}).get("enabled")]

    def _poll(self) -> None:
        """轮询所有已开启通道的勾选测量项（真机模式；仿真模式的读数由仿真计算）。"""
        if self._sim_mode or not callable(self._measure_sink):
            return
        updated = False
        for ch in self._enabled_channels():
            for item, on in self._measure_items.items():
                if not on:
                    continue
                raw = ""
                try:
                    raw = self._measure_sink(item, ch) or ""
                except Exception:  # noqa: BLE001
                    raw = ""
                self._readouts[(ch, item)] = (parse_measure_value(raw) if raw else None, raw)
                updated = True
        if updated:
            self._measure_seq += 1
            self.measurementsChanged.emit()

    @Slot(int)
    def setPollChannel(self, channel: int) -> None:
        self._poll_channel = int(channel)
        self._measure_seq += 1
        self.measurementsChanged.emit()
        self._poll()  # 切换通道后立即读一次，不用等下一秒

    # ---------- 属性 ----------
    @Property(bool, notify=runningChanged)
    def running(self) -> bool:
        return self._running

    @Property(str, notify=stateChanged)
    def timebaseText(self) -> str:
        return _fmt_seconds(self._time_scale) + "/div"

    @Property(str, notify=stateChanged)
    def sourceLabel(self) -> str:
        if self._sim_mode:
            return "仿真波形"
        return "真机波形" if self._waveform_on else "波形未接入"

    @Property(bool, notify=stateChanged)
    def simulationMode(self) -> bool:
        return self._sim_mode

    @Property(str, notify=commandChanged)
    def commandText(self) -> str:
        return self._command_text

    @Property(str, notify=commandChanged)
    def commandState(self) -> str:
        return self._command_state

    @Property(bool, notify=stateChanged)
    def measureStat(self) -> bool:
        return self._measure_stat

    @Property(bool, notify=stateChanged)
    def waveformOn(self) -> bool:
        return self._sim_on if self._sim_mode else self._waveform_on

    @Property(int, notify=stateChanged)
    def stateSeq(self) -> int:
        return self._state_seq

    @Property(int, notify=measurementsChanged)
    def measureSeq(self) -> int:
        return self._measure_seq

    # ---------- 通道设置 ----------
    @Slot(int, bool)
    def setChannelEnabled(self, channel: int, enabled: bool) -> None:
        if channel in self._ch:
            self._ch[channel]["enabled"] = bool(enabled)
            self.channelsChanged.emit()
            self._apply(sc.channel_display(channel, enabled))

    @Slot(int, float)
    def setChannelScale(self, channel: int, volts_per_div: float) -> None:
        if channel in self._ch:
            self._ch[channel]["scale"] = float(volts_per_div)
            self._touch()
            self._apply(sc.channel_scale(channel, volts_per_div))

    @Slot(int, float)
    def setChannelOffset(self, channel: int, volts: float) -> None:
        if channel in self._ch:
            self._ch[channel]["offset"] = float(volts)
            self._touch()
            self._apply(sc.channel_offset(channel, volts))

    @Slot(int, str)
    def setChannelCoupling(self, channel: int, coupling: str) -> None:
        if channel in self._ch:
            self._ch[channel]["coupling"] = str(coupling)
            self._touch()
            self._apply(sc.channel_coupling(channel, coupling))

    @Slot(int, float)
    def setChannelProbe(self, channel: int, ratio: float) -> None:
        if channel in self._ch:
            self._ch[channel]["probe"] = float(ratio)
            self._touch()
            self._apply(sc.channel_probe(channel, ratio))

    @Slot(int, bool)
    def setChannelBwLimit(self, channel: int, on: bool) -> None:
        if channel in self._ch:
            self._ch[channel]["bwlimit"] = bool(on)
            self._touch()
            self._apply(sc.channel_bwlimit(channel, on))

    @Slot(int, bool)
    def setChannelInvert(self, channel: int, on: bool) -> None:
        if channel in self._ch:
            self._ch[channel]["invert"] = bool(on)
            self._touch()
            self._apply(sc.channel_invert(channel, on))

    # ---------- 水平 ----------
    @Slot(float)
    def setTimeScale(self, seconds_per_div: float) -> None:
        self._time_scale = float(seconds_per_div)
        self._touch()
        self._apply(sc.timebase_scale(seconds_per_div))

    @Slot(float)
    def setTimeOffset(self, seconds: float) -> None:
        self._time_offset = float(seconds)
        self._touch()
        self._apply(sc.timebase_offset(seconds))

    # ---------- 触发 ----------
    @Slot(str)
    def setTriggerSweep(self, mode: str) -> None:
        self._trigger["sweep"] = str(mode)
        self._touch()
        self._apply(sc.trigger_sweep(mode))

    @Slot(int)
    def setTriggerSource(self, channel: int) -> None:
        self._trigger["source"] = int(channel)
        self._touch()
        self._apply(sc.trigger_source(channel))

    @Slot(str)
    def setTriggerSlope(self, slope: str) -> None:
        self._trigger["slope"] = str(slope)
        self._touch()
        self._apply(sc.trigger_slope(slope))

    @Slot(float)
    def setTriggerLevel(self, volts: float) -> None:
        self._trigger["level"] = float(volts)
        self._touch()
        self._apply(sc.trigger_level(volts))

    # ---------- 采集 ----------
    @Slot(bool)
    def setRunning(self, running: bool) -> None:
        running = bool(running)
        if self._running != running:
            self._running = running
            self.runningChanged.emit()
        self._apply(sc.run() if running else sc.stop())

    @Slot()
    def singleShot(self) -> None:
        self._running = True
        self.runningChanged.emit()
        self._apply(sc.single())

    @Slot()
    def forceTrigger(self) -> None:
        self._apply(sc.force_trigger())

    @Slot()
    def autoSet(self) -> None:
        self._apply(sc.autoset())

    @Slot()
    def clearScope(self) -> None:
        self._apply(sc.clear())

    # ---------- 测量 ----------
    @Slot(str, bool)
    def setMeasureItem(self, name: str, on: bool) -> None:
        key = str(name).lower()
        if key in self._measure_items:
            self._measure_items[key] = bool(on)
            self._touch()
            if on:
                self._apply(sc.measure_item(key, self._trigger["source"]))
            else:
                self._apply(sc.measure_clear())
            self._measure_seq += 1
            self.measurementsChanged.emit()

    @Slot(bool)
    def setMeasureStat(self, on: bool) -> None:
        self._measure_stat = bool(on)
        self._touch()
        self._apply(sc.measure_stat_display(on))

    @Slot()
    def measureReset(self) -> None:
        self._apply(sc.measure_stat_reset())

    # ---------- 内置信号源 ----------
    @Slot(str)
    def setAfgFunction(self, name: str) -> None:
        self._afg["function"] = str(name)
        self._touch()
        self._apply(sc.afg_function(name))

    @Slot(float)
    def setAfgFrequency(self, hz: float) -> None:
        self._afg["freq"] = float(hz)
        self._touch()
        self._apply(sc.afg_frequency(hz))

    @Slot(float)
    def setAfgAmplitude(self, vpp: float) -> None:
        self._afg["amp"] = float(vpp)
        self._touch()
        self._apply(sc.afg_amplitude(vpp))

    @Slot(float)
    def setAfgOffset(self, volts: float) -> None:
        self._afg["offset"] = float(volts)
        self._touch()
        self._apply(sc.afg_offset(volts))

    @Slot(bool)
    def setAfgOutput(self, on: bool) -> None:
        self._afg["output"] = bool(on)
        self._touch()
        self._apply(sc.afg_output(on))

    # ---------- 读取（供 QML） ----------
    @Slot(int, result=bool)
    def channelEnabled(self, channel: int) -> bool:
        return bool(self._ch.get(int(channel), {}).get("enabled", False))

    @Slot(int, result=float)
    def channelScale(self, channel: int) -> float:
        return float(self._ch.get(int(channel), {}).get("scale", 1.0))

    @Slot(int, result=float)
    def channelOffset(self, channel: int) -> float:
        return float(self._ch.get(int(channel), {}).get("offset", 0.0))

    @Slot(int, result=str)
    def channelCoupling(self, channel: int) -> str:
        return str(self._ch.get(int(channel), {}).get("coupling", "DC"))

    @Slot(int, result=float)
    def channelProbe(self, channel: int) -> float:
        return float(self._ch.get(int(channel), {}).get("probe", 1.0))

    @Slot(int, result=bool)
    def channelBwLimit(self, channel: int) -> bool:
        return bool(self._ch.get(int(channel), {}).get("bwlimit", False))

    @Slot(int, result=bool)
    def channelInvert(self, channel: int) -> bool:
        return bool(self._ch.get(int(channel), {}).get("invert", False))

    @Slot(int, result=str)
    def channelColor(self, channel: int) -> str:
        return _COLORS.get(int(channel), "#ffffff")

    @Slot(int, result=str)
    def channelText(self, channel: int) -> str:
        ch = int(channel)
        if ch not in self._ch:
            return ""
        return "CH%d  %s/div" % (ch, _fmt_volts(self._ch[ch]["scale"]))

    @Slot(result=float)
    def timeScale(self) -> float:
        return self._time_scale

    @Slot(result=float)
    def timeOffset(self) -> float:
        return self._time_offset

    @Slot(result=str)
    def triggerSweep(self) -> str:
        return self._trigger["sweep"]

    @Slot(result=int)
    def triggerSource(self) -> int:
        return self._trigger["source"]

    @Slot(result=str)
    def triggerSlope(self) -> str:
        return self._trigger["slope"]

    @Slot(result=float)
    def triggerLevel(self) -> float:
        return self._trigger["level"]

    @Slot(str, result=bool)
    def measureItemEnabled(self, name: str) -> bool:
        return bool(self._measure_items.get(str(name).lower(), False))

    @Slot(result=str)
    def afgFunction(self) -> str:
        return self._afg["function"]

    @Slot(result=float)
    def afgFrequency(self) -> float:
        return self._afg["freq"]

    @Slot(result=float)
    def afgAmplitude(self) -> float:
        return self._afg["amp"]

    @Slot(result=float)
    def afgOffset(self) -> float:
        return self._afg["offset"]

    @Slot(result=bool)
    def afgOutput(self) -> bool:
        return self._afg["output"]

    @Slot(int, result="QVariantList")
    def samples(self, channel: int) -> List[float]:
        """返回当前数据源的波形采样：仿真模式=生成波形；真机模式=:WAVeform 下载数据。"""
        ch = int(channel)
        if self._sim_mode:
            if not self._sim_on:
                return []
            return list(self._sim_samples.get(ch, []))
        if not self._waveform_on:
            return []
        return list(self._wave_samples.get(ch, []))

    # ---------- 真机读数文本 ----------
    @Slot(int, result=str)
    def measurementText(self, channel: int) -> str:
        ch = int(channel)
        lines = []
        for key, label in _MEASURE_LABELS:
            if not self._measure_items.get(key, False):
                continue
            value, raw = self._readouts.get((ch, key), (None, ""))
            if value is None:
                text = "无效" if raw else "—"
            elif key in ("vpp", "vrms", "vavg"):
                text = "%.3f V" % value
            elif key == "freq":
                text = _fmt_freq(value)
            elif key in ("per", "rtime", "ftime"):
                text = _fmt_seconds(value)
            elif key == "duty":
                text = "%.1f %%" % value
            else:
                text = str(value)
            lines.append("%-5s %s" % (label, text))
        return "\n".join(lines) if lines else "（未勾选测量项）"









