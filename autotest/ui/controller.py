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
    flowChanged = Signal()
    reportChanged = Signal()
    instrumentsChanged = Signal()

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
        self._instrument_defs = []
        self._visible = {}
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
        for cfg in self._instrument_defs:
            kind = cfg.get("type", "")
            mode = "仿真" if cfg.get("simulate") else "真机"
            parts.append("%s(%s/%s)" % (cfg.get("model") or cfg.get("id"), kind, mode))
        return " | ".join(parts) if parts else "（未配置仪器）"

    @Property(bool, notify=flowChanged)
    def flowLoaded(self) -> bool:
        """是否已加载流程（左区流程编辑区据此显示状态）。"""
        return self._flow is not None

    @Property(str, notify=flowChanged)
    def flowName(self) -> str:
        return (self._flow or {}).get("name", "")

    @Property(bool, constant=True)
    def usesSimulation(self) -> bool:
        """配置的示波器是否为 mock（无真机）——决定界面波形/读数的数据源。"""
        for cfg in self._instrument_defs:
            if cfg.get("type") == "rigol_dho":
                return bool(cfg.get("simulate", False))
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

        # 仪器来源：注册表 config/instruments.json（推荐，支持多仪器）；
        # 无注册表时回退到旧的 app_config.json -> instruments 扁平配置。
        from ..core.config import load_instruments

        defs = load_instruments()
        if defs:
            for cfg in defs:
                iid = cfg.get("id")
                if not iid:
                    continue
                self._instrument_defs.append(cfg)
                self._instruments[iid] = create_instrument(iid, cfg)
        else:
            for name, icfg in self._config.get("instruments", {}).items():
                cfg = dict(icfg)
                cfg.setdefault("id", name)
                cfg.setdefault("name", name)
                self._instrument_defs.append(cfg)
                self._instruments[name] = create_instrument(name, icfg)

        self._visible = {cfg["id"]: bool(cfg.get("visible", True)) for cfg in self._instrument_defs}

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
                self.flowChanged.emit()
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
                self.reportChanged.emit()
                info["result"] = "status=%s, %d 条测量" % (result.status, len(result.measurements))
            except Exception as exc:  # noqa: BLE001
                self._set_status("失败: %s" % exc)
                info["result"] = str(exc)
                info["status"] = "error"

    # ---------- 仪器面板 -> 仪器命令下发 ----------
    def _instrument_def(self, iid: str):
        for cfg in self._instrument_defs:
            if cfg.get("id") == iid:
                return cfg
        return None

    def _scope_instrument_id(self):
        for cfg in self._instrument_defs:
            if cfg.get("type") == "rigol_dho":
                return cfg.get("id")
        return None

    def _scope_instrument(self):
        """返回示波器仪器实例（真机或仿真）；未配置时返回 None。"""
        iid = self._scope_instrument_id()
        return self._instruments.get(iid) if iid else None

    def _dispatch_instrument_command(self, iid: str, command: str) -> str:
        """通用命令下发：真机写命令后回读错误队列；仿真仪器只应用并回显。"""
        inst = self._instruments.get(iid)
        if inst is None:
            return "未注册仪器 %s：%s" % (iid, command)
        is_mock = type(inst).__name__.startswith("Mock")
        label = "仿真" if is_mock else "真机"
        try:
            with self._scope_lock:
                if getattr(inst, "_sock", None) is None:
                    inst.initialize()
                if command.endswith("?"):
                    resp = inst.query(command)
                    return "%s %s ⇒ %s" % (label, command, resp.strip())
                inst.write(command)
                if is_mock:
                    return "%s %s ✓（虚拟仪器）" % (label, command)
                try:
                    err = inst.query(":SYSTem:ERRor?").strip()
                except Exception:  # noqa: BLE001
                    err = ""
                if err and not err.startswith("0"):
                    return "%s %s ⚠ 错误队列: %s" % (label, command, err)
                return "%s %s ✓" % (label, command)
        except Exception as exc:  # noqa: BLE001
            return "下发失败 %s：%s" % (command, exc)

    @Slot(str, result=str)
    def sendScopeCommand(self, command: str) -> str:
        """示波器面板命令（兼容旧接口；内部走通用下发）。"""
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
        iid = self._scope_instrument_id()
        if iid is None:
            return "未配置示波器仪器: %s" % command
        return self._dispatch_instrument_command(iid, command)

    # ---------- 仪器注册表（多仪器） ----------
    @Slot(result="QVariantList")
    def instruments(self):
        """仪器注册表信息（供仪器坞勾选显示与架构台展示）。"""
        rows = []
        for cfg in self._instrument_defs:
            iid = cfg.get("id", "")
            rows.append({
                "id": iid,
                "name": cfg.get("name", iid),
                "model": cfg.get("model", ""),
                "type": cfg.get("type", ""),
                "panel": cfg.get("panel", ""),
                "simulate": bool(cfg.get("simulate", False)),
                "visible": bool(self._visible.get(iid, True)),
                "capabilities": ",".join(cfg.get("capabilities", [])),
                "connected": iid in self._instruments,
            })
        return rows

    @Slot(str, result=bool)
    def instrumentVisible(self, iid: str) -> bool:
        return bool(self._visible.get(str(iid), True))

    @Slot(str, bool)
    def setInstrumentVisible(self, iid: str, visible: bool) -> None:
        iid = str(iid)
        self._visible[iid] = bool(visible)
        bus.publish("ui", "action", "instrumentVisible:" + iid, detail="visible=%s" % bool(visible))
        self.instrumentsChanged.emit()

    @Slot(str, str, result=str)
    def sendInstrumentCommand(self, iid: str, command: str) -> str:
        """通用仪器命令下发（电源等非示波器仪器使用）。"""
        command = (command or "").strip()
        if not command:
            return ""
        info: dict = {}
        with bus.span("glue", "slot", "instrumentCommand", detail="%s %s" % (iid, command), info=info):
            text = self._dispatch_instrument_command(str(iid), command)
            info["result"] = text
        self._last_command = text
        self.lastCommandChanged.emit(text)
        return text

    @Slot(str, str, result=str)
    def queryInstrument(self, iid: str, command: str) -> str:
        """通用仪器查询（返回原始字符串；失败返回空串）。"""
        inst = self._instruments.get(str(iid))
        if inst is None:
            return ""
        with bus.quiet():
            try:
                with self._scope_lock:
                    if getattr(inst, "_sock", None) is None:
                        inst.initialize()
                    return inst.query(command).strip()
            except Exception:  # noqa: BLE001
                return ""

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

    @Slot(result="QVariantList")
    def flowSteps(self):
        """流程步骤（阶段2 只读展示；阶段4 支持编辑）。"""
        rows = []

        def walk(items, prefix=""):
            for idx, step in enumerate(items, 1):
                seq = "%s%d" % (prefix, idx)
                step_type = step.get("type", "")
                if step_type == "measure":
                    summary = "%s · %s" % (step.get("instrument", ""), step.get("method", ""))
                elif step_type == "loop":
                    summary = "循环 ×%s" % step.get("count", 1)
                elif step_type == "branch":
                    summary = "条件分支"
                else:
                    summary = str(step.get("params", ""))[:40]
                rows.append({
                    "seq": seq,
                    "stepType": step_type,
                    "summary": summary,
                })
                if step_type == "loop":
                    walk(step.get("body", []), seq + ".")

        walk((self._flow or {}).get("steps", []))
        return rows

    @Slot(str)
    def manualAction(self, name: str) -> None:
        """左区手动动作（阶段2 仅记录事件；阶段3/4 接入虚拟电源与流程控制）。"""
        bus.publish("ui", "action", "manual:" + str(name), detail="阶段3/4 接入后生效")
        self._set_status("手动动作: %s（阶段3/4 接入后生效）" % name)

    @Slot(result="QVariantList")
    def reportRows(self):
        """右侧报表总表数据（阶段2：展示本次测量；阶段5 增加列映射与判据）。"""
        rows = []
        if self._last_result is not None:
            for m in self._last_result.measurements:
                rows.append({
                    "name": m.name,
                    "value": "" if m.value is None else ("%.6g" % m.value),
                    "unit": m.unit,
                    "verdict": "—",
                })
        return rows
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









