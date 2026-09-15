"""QML <-> Python 桥接控制器。

通过 setContextProperty 暴露给 QML；QML 调用其 Slot，Python 侧通过 Signal
把状态与测量结果推回界面，形成双向桥接。

除流程执行外，还承担“示波器面板设置 -> 真机 SCPI 命令”的下发（sendScopeCommand）。
"""
from __future__ import annotations

import threading
from typing import Optional

from PySide6.QtCore import Property, QObject, Signal, Slot

from ..bus.event_bus import bus


class TestController(QObject):
    statusChanged = Signal(str)
    resultAdded = Signal(str)
    flowFinished = Signal(str)
    lastCommandChanged = Signal(str)

    def __init__(
        self,
        config_path: str = "config/app_config.json",
        flow_path: str = "config/flow_sample.json",
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._config_path = config_path
        self._flow_path = flow_path
        self._status = "就绪"
        self._flow = None
        self._instruments = {}
        self._store = None
        self._last_result = None
        self._last_command = ""
        self._scope_lock = threading.Lock()
        self._load_config()

    # ---------- 供 QML 读取的属性 ----------
    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(str, constant=True)
    def instrumentInfo(self) -> str:
        """当前配置的仪器摘要（用于界面显示，只读）。"""
        parts = []
        for name, icfg in self._config.get("instruments", {}).items():
            kind = icfg.get("type", "mock")
            if kind == "rigol_dho":
                parts.append("%s: rigol_dho %s:%s" % (name, icfg.get("host"), icfg.get("port")))
            elif kind == "mock":
                parts.append("%s: mock（DHO924S 仿真）" % name)
            else:
                parts.append("%s: %s" % (name, kind))
        return " | ".join(parts) if parts else "（未配置仪器）"

    @Property(bool, constant=True)
    def usesSimulation(self) -> bool:
        """配置的示波器是否为 mock（无真机）——决定界面波形/读数的数据源。"""
        for _name, icfg in self._config.get("instruments", {}).items():
            if icfg.get("type") == "rigol_dho":
                return False
        return True

    @Property(str, notify=lastCommandChanged)
    def lastCommandText(self) -> str:
        """最近一次下发的 SCPI 命令及其结果（供界面显示）。"""
        return self._last_command

    # ---------- 内部初始化 ----------
    def _load_config(self) -> None:
        from ..core.config import load_app_config
        from ..data.store import LocalStore
        from ..hal.factory import create_instrument

        self._config = load_app_config(self._config_path)
        for name, icfg in self._config.get("instruments", {}).items():
            self._instruments[name] = create_instrument(name, icfg)

        db_path = self._config.get("data", {}).get("db_path", "data/test.db")
        self._store = LocalStore(db_path)
        self._store.open()

    def _ensure_instruments_ready(self) -> None:
        for inst in self._instruments.values():
            try:
                inst.initialize()
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError("仪器初始化失败: %s" % exc)

    def _set_status(self, text: str) -> None:
        self._status = text
        self.statusChanged.emit(text)

    # ---------- 供 QML 调用的槽函数 ----------
    @Slot(str)
    def loadFlow(self, path: str) -> None:
        from ..core.config import load_flow

        bus.publish("ui", "action", "loadFlow", detail=path)
        info: dict = {}
        with bus.span("glue", "slot", "loadFlow", detail=path, info=info):
            try:
                self._flow = load_flow(path)
                self._set_status("已加载流程: %s" % path)
                info["result"] = "已加载"
            except Exception as exc:  # noqa: BLE001
                self._set_status("加载流程失败: %s" % exc)
                info["result"] = str(exc)
                info["status"] = "error"

    @Slot()
    def runFlow(self) -> None:
        bus.publish("ui", "action", "runFlow")
        if self._flow is None:
            self._set_status("请先加载流程")
            bus.publish("glue", "slot", "runFlow", status="skip", result="未加载流程")
            return
        self._set_status("运行中")
        bus.publish("glue", "slot", "runFlow", result="已启动后台线程")
        threading.Thread(target=self._run_flow_worker, daemon=True).start()

    def _run_flow_worker(self) -> None:
        from ..core.engine import ExecutionEngine

        info: dict = {}
        with bus.span("glue", "worker", "runFlow", detail=self._flow.get("flow_id", ""), info=info):
            try:
                self._ensure_instruments_ready()
                engine = ExecutionEngine(self._instruments)
                result = engine.run_flow(self._flow)

                for m in result.measurements:
                    if m.value is not None:
                        self.resultAdded.emit("%s = %s %s" % (m.name, m.value, m.unit))
                    else:
                        self.resultAdded.emit("%s: %s" % (m.name, m.raw_value))

                self._last_result = result
                self._store.save_result(result)
                self._set_status("完成: %s" % result.status)
                self.flowFinished.emit(result.test_id)
                info["result"] = "status=%s, %d 条测量" % (result.status, len(result.measurements))
            except Exception as exc:  # noqa: BLE001
                self._set_status("失败: %s" % exc)
                info["result"] = str(exc)
                info["status"] = "error"

    # ---------- 示波器面板 -> 真机 SCPI 下发 ----------
    def _scope_instrument(self):
        """返回配置为 rigol_dho 的仪器；mock/未配置时返回 None。"""
        for name, icfg in self._config.get("instruments", {}).items():
            if icfg.get("type") == "rigol_dho":
                return self._instruments.get(name)
        return None

    @Slot(str, result=str)
    def sendScopeCommand(self, command: str) -> str:
        """把界面产生的 SCPI 命令下发到真机；仿真模式下只回显。"""
        command = (command or "").strip()
        if not command:
            return ""
        info: dict = {}
        with bus.span("glue", "slot", "sendScopeCommand", detail=command, info=info):
            text = self._dispatch_scope_command(command)
            info["result"] = text
        self._last_command = text
        self.lastCommandChanged.emit(text)
        return text

    def _dispatch_scope_command(self, command: str) -> str:
        inst = self._scope_instrument()
        if inst is None:
            text = "已应用(仿真): %s" % command
        else:
            try:
                with self._scope_lock:
                    if getattr(inst, "_sock", None) is None:
                        inst.initialize()
                    if command.endswith("?"):
                        resp = inst.query(command)
                        text = "真机 %s ⇒ %s" % (command, resp.strip())
                    else:
                        inst.write(command)
                        # 写命令后查一次错误队列：命令拼写错误会立刻暴露，便于核对手册
                        try:
                            err = inst.query(":SYSTem:ERRor?").strip()
                        except Exception:  # noqa: BLE001
                            err = ""
                        if err and not err.startswith("0"):
                            text = "真机 %s ⚠ 错误队列: %s" % (command, err)
                        else:
                            text = "真机 %s ✓" % command
            except Exception as exc:  # noqa: BLE001
                text = "下发失败 %s：%s" % (command, exc)
        return text

    @Slot(str, int, result=str)
    def queryScopeItem(self, item: str, channel: int) -> str:
        """按 (测量项, 通道) 查询真机测量值，返回原始字符串。

        供界面“自动测量”轮询使用（:MEASure:ITEM? <item>,CHANnel<n>）；
        未配置真机或查询失败时返回空串，界面显示为“—”。
        """
        from ..core import scope_commands

        inst = self._scope_instrument()
        if inst is None:
            return ""
        # 周期性轮询：静默上下文（事件只计数，不进架构台日志，避免淹没关键链路）
        with bus.quiet():
            try:
                with self._scope_lock:
                    if getattr(inst, "_sock", None) is None:
                        inst.initialize()
                    return inst.query(scope_commands.measure_item_query(item, channel)).strip()
            except Exception:  # noqa: BLE001
                return ""

    @Slot(int, result="QVariantList")
    def readScopeWaveform(self, channel: int):
        """读取真机屏幕波形（电压数组，:WAVeform 族）；失败或未配置真机时返回空列表。"""
        inst = self._scope_instrument()
        if inst is None or not hasattr(inst, "read_waveform"):
            return []
        # 周期性波形下载：静默上下文（只计数，不进日志）
        with bus.quiet():
            try:
                with self._scope_lock:
                    if getattr(inst, "_sock", None) is None:
                        inst.initialize()
                    return list(inst.read_waveform(int(channel)))
            except Exception:  # noqa: BLE001
                return []

    @Slot(str)
    def saveReport(self, path: str = "reports/report.html") -> None:
        from ..report.html_report import save

        bus.publish("ui", "action", "saveReport", detail=path)
        info: dict = {}
        with bus.span("glue", "slot", "saveReport", detail=path, info=info):
            if self._last_result is None:
                self._set_status("没有可保存的结果")
                info["result"] = "无可保存结果"
                info["status"] = "skip"
                return
            try:
                saved = save(self._last_result.to_dict(), path)
                self._set_status("报告已保存: %s" % saved)
                info["result"] = saved
            except Exception as exc:  # noqa: BLE001
                self._set_status("保存报告失败: %s" % exc)
                info["result"] = str(exc)
                info["status"] = "error"






