"""测试执行引擎：把流程定义解释为实际执行动作（阶段4 扩展版）。

支持的步骤类型（9 类）：
  measure      测量（方法库 / 能力动作）
  action       能力动作（含 power_on / power_off / set_param 简写）
  wait         等待（可被停止打断）
  compute      波形计算 / 算法（一期算法库）
  limit_check  限值判定（Pass/Fail，结果写入 TestResult.verdicts）
  store        存库（记录变量）
  report       填报表（记录列映射）
  loop         循环
  branch       条件分支

运行控制（ExecutionControl）语义：
  暂停 = 当前步骤结束后停在边界，**不执行任何动作**，等待继续；
  停止 = 停止调度后续步骤，并**自动回安全态**（各仪器安全动作）；
  单步 = 每个步骤边界停一次。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from ..bus.event_bus import bus
from . import algorithms as alg
from . import capabilities as cap
from .methods import get_method
from .models import Measurement, TestResult

# 兼容简写步骤类型 -> 能力动作
_SHORTCUTS = {
    "power_on": "power.output_on",
    "power_off": "power.output_off",
}


class FlowStopped(Exception):
    """用户请求停止流程。"""


class ExecutionControl:
    """流程运行控制：暂停 / 继续 / 停止 / 单步。"""

    def __init__(self) -> None:
        self._resume = threading.Event()
        self._resume.set()
        self._stop = threading.Event()
        self._step_continue = threading.Event()
        self._step_continue.set()
        self._step_mode = False
        self._first = True
        self._paused = False

    # ---------- 查询 ----------
    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def step_mode(self) -> bool:
        return self._step_mode

    @property
    def stop_requested(self) -> bool:
        return self._stop.is_set()

    # ---------- 控制（由界面调用） ----------
    def begin_run(self) -> None:
        """开始一次运行：清除停止标记、恢复运行；保留单步模式设置。"""
        self._stop.clear()
        self._step_continue.set()
        self._resume.set()
        self._paused = False
        self._first = True

    def pause(self) -> None:
        self._paused = True
        self._resume.clear()
        bus.publish("app", "control", "pause", result="将在步骤边界暂停（暂停期间不执行动作）")

    def resume(self) -> None:
        self._paused = False
        self._resume.set()
        bus.publish("app", "control", "resume")

    def request_stop(self) -> None:
        self._stop.set()
        self._resume.set()
        self._step_continue.set()
        bus.publish("app", "control", "stop", result="停止并回安全态")

    def enable_step(self, on: bool = True) -> None:
        self._step_mode = bool(on)
        self._first = True
        self._resume.set()
        bus.publish("app", "control", "stepMode", detail="单步=%s" % self._step_mode)

    def step_continue(self) -> None:
        """放行一个步骤（单步模式下使用）。"""
        self._step_continue.set()
        bus.publish("app", "control", "stepContinue")

    # ---------- 引擎在步骤边界调用 ----------
    def wait_point(self) -> None:
        if self._stop.is_set():
            raise FlowStopped()
        # 暂停：等待继续（此期间不下发任何命令、不采集、不计算）
        while not self._resume.wait(0.05):
            if self._stop.is_set():
                raise FlowStopped()
        # 单步：除第一步外，每个步骤边界等一次"继续"
        if self._step_mode and not self._first:
            self._step_continue.clear()
            while not self._step_continue.wait(0.05):
                if self._stop.is_set():
                    raise FlowStopped()
        self._first = False


class ExecutionEngine:
    def __init__(
        self,
        instruments: Optional[Dict[str, Any]] = None,
        control: Optional[ExecutionControl] = None,
        defs: Optional[List[Dict[str, Any]]] = None,
        on_step: Optional[Callable[[str, str], None]] = None,
    ):
        self.instruments = instruments or {}
        self.control = control or ExecutionControl()
        self.defs = defs or []
        self.on_step = on_step

    # ---------- 主流程 ----------
    def run_flow(self, flow: Dict[str, Any], dut_info: Optional[Dict[str, Any]] = None) -> TestResult:
        test_id = flow.get("flow_id", "flow") + "-" + uuid.uuid4().hex[:8]
        result = TestResult(
            test_id=test_id,
            dut_info=dut_info or flow.get("dut_info", {}),
            test_conditions=flow.get("test_conditions", {}),
            status="running",
        )
        variables: Dict[str, Any] = {}

        self.control.begin_run()
        bus.set_correlation(test_id)
        info: Dict[str, Any] = {}
        with bus.span("app", "flow", flow.get("flow_id", "flow"),
                      detail=flow.get("name", ""), info=info):
            try:
                self._run_steps(flow.get("steps", []), result, variables)
                result.finish("passed")
                info["result"] = "passed, %d 条测量 / %d 条判定" % (
                    len(result.measurements), len(result.verdicts))
            except FlowStopped:
                safe = cap.restore_safe_state(self.instruments, self.defs)
                result.finish("stopped", "已停止并回安全态：" + ("；".join(safe) if safe else "无"))
                info["result"] = "stopped"
                info["status"] = "skip"
            except Exception as exc:  # noqa: BLE001
                result.finish("failed", str(exc))
                info["result"] = "failed: %s" % exc
                info["status"] = "error"
        return result

    # ---------- 步骤调度 ----------
    def _run_steps(self, steps: List[Dict[str, Any]], result: TestResult, variables: Dict[str, Any]) -> None:
        for step in steps:
            self.control.wait_point()          # 步骤边界：处理停止/暂停/单步
            self._run_step(step, result, variables)

    def _run_step(self, step: Dict[str, Any], result: TestResult, variables: Dict[str, Any]) -> None:
        step_type = step.get("type")
        step_id = step.get("id", "")
        if self.on_step is not None:
            try:
                self.on_step(step_id, str(step_type))
            except Exception:  # noqa: BLE001
                pass
        with bus.span("app", "step", str(step_type), detail=step_id):
            if step_type == "measure":
                self._run_measure(step, result, variables)

            elif step_type in ("action", "power_on", "power_off", "set_param"):
                self._run_action(step, result, variables)

            elif step_type == "wait":
                self._run_wait(step)

            elif step_type == "compute":
                self._run_compute(step, variables)

            elif step_type == "limit_check":
                self._run_limit_check(step, result, variables)

            elif step_type == "store":
                self._run_store(step, result, variables)

            elif step_type == "report":
                self._run_report(step, result, variables)

            elif step_type == "loop":
                count = int(step.get("count", 1))
                for _ in range(count):
                    self._run_steps(step.get("body", []), result, variables)

            elif step_type == "branch":
                if self._condition_true(step.get("condition"), variables):
                    self._run_steps(step.get("then", []), result, variables)
                else:
                    self._run_steps(step.get("else", []), result, variables)

            else:
                raise ValueError("未知步骤类型: %r" % step_type)

    # ---------- 各步骤实现 ----------
    def _instrument(self, iid: str):
        inst = self.instruments.get(iid)
        if inst is None:
            raise KeyError("流程引用了未配置的仪器: %r" % iid)
        return inst

    def _run_measure(self, step: Dict[str, Any], result: TestResult, variables: Dict[str, Any]) -> None:
        instrument_id = step.get("instrument")
        instrument = self._instrument(instrument_id)
        method = get_method(step.get("method"))
        info: Dict[str, Any] = {}
        with bus.span("app", "method", str(step.get("method")),
                      detail="%s @ %s" % (step.get("method"), instrument_id), info=info):
            measurement = method(instrument, step.get("params", {}))
            info["result"] = "%s = %s %s" % (measurement.name, measurement.value, measurement.unit)
        if not measurement.instrument_id:
            measurement.instrument_id = instrument_id
        result.measurements.append(measurement)
        if measurement.name:
            variables[measurement.name] = (measurement.value if measurement.value is not None
                                           else measurement.raw_value)

    def _run_action(self, step: Dict[str, Any], result: TestResult, variables: Dict[str, Any]) -> None:
        action_id = step.get("action") or _SHORTCUTS.get(step.get("type", ""), "")
        instrument_id = step.get("instrument")
        instrument = self._instrument(instrument_id)
        params = {k: self._resolve(v, variables) for k, v in (step.get("params") or {}).items()}
        spec = cap.action(action_id)
        res = cap.execute(instrument, action_id, params)
        if not res.get("ok"):
            raise RuntimeError("动作失败 %s: %s" % (action_id, res.get("detail")))
        name = step.get("name") or action_id
        variables[name] = res.get("value")
        # 读取类动作（kind=measure）登记为测量结果
        if spec and spec.get("kind") == "measure":
            result.measurements.append(Measurement(
                name=name,
                value=_to_float(res.get("value")),
                unit=res.get("unit", ""),
                instrument_id=instrument_id,
                raw_value=res.get("detail", ""),
            ))

    def _run_wait(self, step: Dict[str, Any]) -> None:
        seconds = float(step.get("seconds", step.get("params", {}).get("seconds", 0)) or 0)
        deadline = time.time() + max(0.0, seconds)
        while time.time() < deadline:
            if self.control.stop_requested:
                raise FlowStopped()
            time.sleep(min(0.05, max(0.0, deadline - time.time())))

    def _run_compute(self, step: Dict[str, Any], variables: Dict[str, Any]) -> None:
        inputs = {k: self._resolve(v, variables) for k, v in (step.get("inputs") or {}).items()}
        ok, value, detail = alg.compute(step.get("algorithm"), inputs, step.get("params", {}))
        if not ok:
            raise RuntimeError("算法失败 %s: %s" % (step.get("algorithm"), detail))
        variables[step.get("output", "result")] = value
        bus.publish("app", "compute", str(step.get("algorithm")), detail=detail, result=str(value)[:60])

    def _run_limit_check(self, step: Dict[str, Any], result: TestResult, variables: Dict[str, Any]) -> None:
        name = str(step.get("variable", ""))
        value = variables.get(name)
        lower = step.get("lower", step.get("min"))
        upper = step.get("upper", step.get("max"))
        passed = value is not None
        v: Optional[float] = None
        if passed:
            v = _to_float(value)
            if v is None:
                passed = False
            else:
                if lower is not None and v < float(lower):
                    passed = False
                if upper is not None and v > float(upper):
                    passed = False
        record = {"name": name, "value": v, "lower": lower, "upper": upper, "passed": bool(passed)}
        result.verdicts.append(record)
        variables["%s_passed" % name] = bool(passed)
        bus.publish("app", "verdict", name,
                    detail="lower=%s upper=%s" % (lower, upper),
                    result="PASS" if passed else "FAIL",
                    status="ok" if passed else "error")
        if not passed and step.get("fail_fast", False):
            raise RuntimeError("限值判定不通过: %s = %s (下限 %s / 上限 %s)" % (name, v, lower, upper))

    def _run_store(self, step: Dict[str, Any], result: TestResult, variables: Dict[str, Any]) -> None:
        name = str(step.get("variable", ""))
        value = self._resolve(step.get("value", variables.get(name)), variables)
        result.measurements.append(Measurement(
            name=step.get("name") or name,
            value=_to_float(value),
            unit=str(step.get("unit", "")),
            instrument_id=str(step.get("instrument", "")),
            raw_value=str(value),
        ))
        bus.publish("data", "write", "store", detail=name, result=str(value)[:60])

    def _run_report(self, step: Dict[str, Any], result: TestResult, variables: Dict[str, Any]) -> None:
        mapping = dict(step.get("mapping") or {})
        resolved = {k: self._resolve(v, variables) for k, v in mapping.items()}
        result.test_conditions.setdefault("report", []).append(resolved)
        bus.publish("report", "mapping", "report", detail=str(resolved)[:120])

    # ---------- 工具 ----------
    @staticmethod
    def _resolve(value: Any, variables: Dict[str, Any]) -> Any:
        """支持在参数里用 "$变量名" 引用前面步骤的结果。"""
        if isinstance(value, str) and value.startswith("$"):
            return variables.get(value[1:], value)
        return value

    @staticmethod
    def _condition_true(condition: Optional[Dict[str, Any]], variables: Dict[str, Any]) -> bool:
        if not condition:
            return True
        left = condition.get("left")
        right = condition.get("right")
        op = condition.get("op", "==")
        actual = variables.get(left)
        if actual is None:
            return False
        if op == "==":
            return actual == right
        if op == "!=":
            return actual != right
        if op == ">":
            return float(actual) > float(right)
        if op == ">=":
            return float(actual) >= float(right)
        if op == "<":
            return float(actual) < float(right)
        if op == "<=":
            return float(actual) <= float(right)
        raise ValueError("未知条件运算符: %r" % op)


def _to_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
