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
from ..core.engine import ExecutionControl


class TestController(QObject):
    statusChanged = Signal(str)
    resultAdded = Signal(str)
    flowFinished = Signal(str)
    lastCommandChanged = Signal(str)
    flowChanged = Signal()
    reportChanged = Signal()
    instrumentsChanged = Signal()
    flowStateChanged = Signal()
    stepChanged = Signal(str)

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
        self._control = ExecutionControl()
        self._report_tpl = None
        self._flow_running = False
        self._current_step = ""
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

    @Property(bool, notify=flowStateChanged)
    def flowRunning(self) -> bool:
        return self._flow_running

    @Property(bool, notify=flowStateChanged)
    def flowPaused(self) -> bool:
        return self._control.paused

    @Property(bool, notify=flowStateChanged)
    def stepMode(self) -> bool:
        return self._control.step_mode

    @Property(str, notify=stepChanged)
    def currentStepId(self) -> str:
        return self._current_step

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
        self._flow_running = True
        self._current_step = ""
        self.flowStateChanged.emit()
        with bus.span("glue", "worker", "runFlow", detail=self._flow.get("flow_id", ""), info=info):
            try:
                self._ensure_instruments_ready()
                engine = ExecutionEngine(self._instruments,
                                         control=self._control,
                                         defs=self._instrument_defs,
                                         on_step=self._on_step)
                result = engine.run_flow(self._flow)
                if result.status == "stopped":
                    power = getattr(self, "_power", None)
                    if power is not None:
                        try:
                            power.syncState()
                        except Exception:  # noqa: BLE001
                            pass

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
            finally:
                self._flow_running = False
                self._current_step = ""
                self.flowStateChanged.emit()
                self.stepChanged.emit("")

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
                if not getattr(inst, "is_connected", False):
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
                    if not getattr(inst, "is_connected", False):
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
                    if not getattr(inst, "is_connected", False):
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
                    if not getattr(inst, "is_connected", False):
                        inst.initialize()
                    return list(inst.read_waveform(int(channel)))
            except Exception:  # noqa: BLE001
                return []

    @Slot(result="QVariantList")
    def flowSteps(self):
        """流程顶层步骤摘要（阶段4：含 index/stepId，供列表与运行高亮）。"""
        from ..core import flow_editor

        if self._flow is None:
            return []
        return flow_editor.summarize(self._flow)

    # ---------- 流程运行控制（阶段4） ----------
    def _on_step(self, step_id: str, step_type: str) -> None:
        """引擎在步骤开始时回调（可能来自后台线程，Qt 会自动排队到界面线程）。"""
        self._current_step = str(step_id)
        self.stepChanged.emit(self._current_step)

    @Slot()
    def pauseFlow(self) -> None:
        if not self._flow_running:
            return
        self._control.pause()
        self._set_status("已请求暂停：当前步骤结束后停在边界（暂停期间不执行动作）")
        self.flowStateChanged.emit()

    @Slot()
    def resumeFlow(self) -> None:
        self._control.resume()
        self._set_status("继续运行")
        self.flowStateChanged.emit()

    @Slot()
    def stopFlow(self) -> None:
        if not self._flow_running:
            return
        self._control.request_stop()
        self._set_status("停止中：将回安全态（电源断电 / 示波器停止采集）")
        self.flowStateChanged.emit()

    @Slot()
    def stepFlow(self) -> None:
        """单步：未运行时以单步模式启动；运行中放行一步。"""
        if not self._flow_running:
            if self._flow is None:
                self._set_status("请先加载流程")
                return
            self._control.enable_step(True)
            self.flowStateChanged.emit()
            self._set_status("单步运行（每步边界暂停）")
            self.runFlow()
        else:
            self._control.step_continue()
            self._set_status("单步：放行一步")

    # ---------- 流程编辑（阶段4） ----------
    @Slot(result="QVariantList")
    def addableSteps(self):
        from ..core import flow_editor

        return flow_editor.addable_actions()

    @Slot(int, result="QVariantList")
    def stepParams(self, index: int):
        from ..core import flow_editor

        if self._flow is None:
            return []
        items = flow_editor.steps(self._flow)
        if not (0 <= int(index) < len(items)):
            return []
        rows = flow_editor.step_params(items[int(index)])
        for row in rows:
            row["stepIndex"] = int(index)
        return rows

    @Slot(str)
    def addStep(self, action_id: str) -> None:
        from ..core import flow_editor

        action_id = str(action_id or "").strip()
        if not action_id:
            return
        if self._flow is None:
            self._flow = {"flow_id": "manual", "name": "手工流程", "steps": []}
        flow_editor.add_step(self._flow, action_id)
        bus.publish("ui", "action", "addStep", detail=action_id)
        self.flowChanged.emit()

    @Slot(int)
    def removeStep(self, index: int) -> None:
        from ..core import flow_editor

        if self._flow is not None and flow_editor.remove_step(self._flow, int(index)):
            bus.publish("ui", "action", "removeStep", detail="index=%d" % int(index))
            self.flowChanged.emit()

    @Slot(int, int)
    def moveStep(self, index: int, delta: int) -> None:
        from ..core import flow_editor

        if self._flow is not None and flow_editor.move_step(self._flow, int(index), int(delta)):
            bus.publish("ui", "action", "moveStep", detail="index=%d delta=%d" % (int(index), int(delta)))
            self.flowChanged.emit()

    @Slot(int, str, str)
    def setStepParam(self, index: int, name: str, value: str) -> None:
        from ..core import flow_editor

        if self._flow is None:
            return
        if flow_editor.set_param(self._flow, int(index), str(name), value):
            bus.publish("ui", "action", "setStepParam", detail="%s=%s" % (name, value))
            self.flowChanged.emit()

    @Slot(str, result=str)
    def saveFlow(self, path: str) -> str:
        import json
        import os

        from ..core.config import resolve_path

        try:
            target = resolve_path(path)
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            with open(target, "w", encoding="utf-8") as fh:
                json.dump(self._flow or {}, fh, ensure_ascii=False, indent=2)
            self._set_status("流程已保存: %s" % target)
            bus.publish("ui", "action", "saveFlow", detail=target)
            return target
        except Exception as exc:  # noqa: BLE001
            self._set_status("保存流程失败: %s" % exc)
            return ""

    @Slot(str)
    def manualAction(self, name: str) -> None:
        """左区手动动作（阶段2 仅记录事件；阶段3/4 接入虚拟电源与流程控制）。"""
        bus.publish("ui", "action", "manual:" + str(name), detail="阶段3/4 接入后生效")
        self._set_status("手动动作: %s（阶段3/4 接入后生效）" % name)

    # ---------- 报表（阶段5：验收记录表样式，配置驱动） ----------
    def _report_template(self):
        """加载报表模板（config/report_template.json，缓存）。"""
        if getattr(self, "_report_tpl", None) is None:
            from ..core.config import load_json, resolve_path

            try:
                self._report_tpl = load_json(resolve_path("config/report_template.json"))
            except Exception:  # noqa: BLE001
                self._report_tpl = {}
        return self._report_tpl

    @Slot(result="QVariantList")
    def reportRows(self):
        """右区报表行（按验收模板展开；无模板时回退为扁平测量）。"""
        from ..report import acceptance as acc_build

        if self._last_result is None:
            return []
        template = self._report_template()
        if not template:
            return [{
                "group": "", "sub": "", "detail": m.name, "spec": "",
                "unit": m.unit,
                "value": "" if m.value is None else ("%.6g" % m.value),
                "verdict": "—", "passed": False,
            } for m in self._last_result.measurements]

        report = acc_build.build_report(template, self._last_result.to_dict())
        rows = []
        for group in report.get("groups", []):
            for sub in group.get("sub_groups", []):
                for row in sub.get("rows", []):
                    rows.append({
                        "group": "%s %s" % (group.get("seq", ""), group.get("item", "")),
                        "sub": sub.get("sub_item", ""),
                        "detail": row.get("detail", ""),
                        "spec": row.get("spec", ""),
                        "unit": row.get("unit", ""),
                        "value": row.get("display", ""),
                        "verdict": "合格" if row.get("passed") else "不合格",
                        "passed": bool(row.get("passed")),
                    })
        return rows

    @Slot(result=str)
    def reportSummary(self) -> str:
        """报表汇总文本（合计/合格/不合格）。"""
        from ..report import acceptance as acc_build

        if self._last_result is None:
            return "尚未运行流程"
        template = self._report_template()
        if not template:
            return ""
        report = acc_build.build_report(template, self._last_result.to_dict())
        s = report.get("summary", {})
        return "合计 %s 项 / 合格 %s 项 / 不合格 %s 项%s" % (
            s.get("total", 0), s.get("passed", 0), s.get("failed", 0),
            "" if s.get("all_passed") else "（存在不合格项）")
    # ---------- 仪器发现（阶段6：一期 + 二期） ----------
    @Slot(result=str)
    def localSubnet(self) -> str:
        from ..hal.discovery import local_subnet_cidr

        return local_subnet_cidr()

    @Slot(str, result="QVariantMap")
    def testInstrumentConnection(self, config_json: str):
        import json

        from ..hal.discovery import test_connection

        try:
            cfg = json.loads(config_json)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": "参数解析失败: %s" % exc, "idn": ""}
        return test_connection(cfg)

    @Slot(str, result="QVariantList")
    def scanInstruments(self, subnet: str):
        from ..hal.discovery import scan_network

        try:
            return scan_network(subnet)
        except Exception as exc:  # noqa: BLE001
            bus.publish("ui", "action", "scanInstruments", detail=subnet,
                        result=str(exc), status="error")
            return []

    @Slot(result="QVariantList")
    def enumerateVisaInstruments(self):
        from ..hal.discovery import enumerate_visa

        return enumerate_visa()

    @Slot(str, result=str)
    def addDiscoveredInstrument(self, item_json: str) -> str:
        import json

        from ..core.config import resolve_path
        from ..hal.discovery import add_instrument_to_registry, make_registry_entry

        try:
            item = json.loads(item_json)
        except Exception as exc:  # noqa: BLE001
            return "参数错误: %s" % exc
        model = str(item.get("model", "")).upper()
        vendor = str(item.get("vendor", "")).upper()
        if "DHO" in model or "RIGOL" in vendor:
            dtype, panel, caps = "rigol_dho", "ScopeInstrument", ["scope"]
        elif "SPD" in model or "SIGLENT" in vendor:
            dtype, panel, caps = "siglent_spd3303x", "PowerSupplyInstrument", ["power"]
        else:
            dtype, panel, caps = "tcp_scpi", "", []
        raw_id = str(item.get("serial") or item.get("host") or item.get("resource") or "new")
        iid = "inst_" + "".join(ch if ch.isalnum() else "_" for ch in raw_id)
        entry = make_registry_entry(item, instrument_id=iid, device_type=dtype, panel=panel)
        entry["capabilities"] = caps
        add_instrument_to_registry(entry, resolve_path("config/instruments.json"))
        self._reload_instrument_defs()
        bus.publish("ui", "action", "addDiscoveredInstrument", detail=entry.get("name", ""))
        return "已添加: %s（%s）" % (entry.get("name", iid), dtype)

    def _reload_instrument_defs(self) -> None:
        from ..core.config import load_instruments
        from ..hal.factory import create_instrument

        defs = load_instruments()
        if not defs:
            return
        existing = {cfg.get("id") for cfg in self._instrument_defs}
        self._instrument_defs = defs
        for cfg in defs:
            iid = cfg.get("id")
            if iid and iid not in existing:
                try:
                    self._instruments[iid] = create_instrument(iid, cfg)
                except Exception:  # noqa: BLE001
                    pass
        self._visible.update({cfg["id"]: bool(cfg.get("visible", True)) for cfg in defs if cfg.get("id")})
        self.instrumentsChanged.emit()

    @Property(str, notify=instrumentsChanged)
    def instrumentSummary(self) -> str:
        return " | ".join("%s(%s)" % (c.get("model") or c.get("id"), c.get("type", ""))
                          for c in self._instrument_defs)
    @Slot(str, result=str)
    def saveReportExcel(self, path: str = "reports/report.xlsx") -> str:
        """Excel 导出（阶段5：接口预留，未实现时给出提示）。"""
        from ..report import html_report as hr
        from ..report.xlsx_export import ExcelExportNotImplemented

        bus.publish("ui", "action", "saveReportExcel", detail=path)
        if self._last_result is None:
            self._set_status("没有可保存的结果")
            return ""
        try:
            saved = hr.save_xlsx(self._last_result.to_dict(), path, template=self._report_template())
            self._set_status("Excel 已保存: %s" % saved)
            return saved
        except ExcelExportNotImplemented:
            self._set_status("Excel 输出接口已预留（当前阶段仅输出 HTML）")
            return ""
        except Exception as exc:  # noqa: BLE001
            self._set_status("Excel 导出失败: %s" % exc)
            return ""

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
                saved = save(self._last_result.to_dict(), path, template=self._report_template())
                self._set_status("报告已保存: %s" % saved)
                info["result"] = saved
            except Exception as exc:  # noqa: BLE001
                self._set_status("保存报告失败: %s" % exc)
                info["result"] = str(exc)
                info["status"] = "error"












