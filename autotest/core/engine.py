"""测试执行引擎：把流程定义解释为实际执行动作。

原型阶段支持步骤类型：
  - measure: 调用方法库中的方法执行一次测量
  - loop:    对 body 子步骤重复 count 次
  - branch:  根据上一次同名测量值选择 then/else 分支（简单条件）
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from .methods import get_method
from .models import Measurement, TestResult


class ExecutionEngine:
    def __init__(self, instruments: Optional[Dict[str, Any]] = None):
        self.instruments = instruments or {}

    def run_flow(self, flow: Dict[str, Any], dut_info: Optional[Dict[str, Any]] = None) -> TestResult:
        test_id = flow.get("flow_id", "flow") + "-" + uuid.uuid4().hex[:8]
        result = TestResult(
            test_id=test_id,
            dut_info=dut_info or flow.get("dut_info", {}),
            test_conditions=flow.get("test_conditions", {}),
            status="running",
        )
        last_values: Dict[str, Any] = {}
        try:
            self._run_steps(flow.get("steps", []), result, last_values)
            result.finish("passed")
        except Exception as exc:  # noqa: BLE001
            result.finish("failed", str(exc))
        return result

    def _run_steps(self, steps: List[Dict[str, Any]], result: TestResult, last_values: Dict[str, Any]) -> None:
        for step in steps:
            self._run_step(step, result, last_values)

    def _run_step(self, step: Dict[str, Any], result: TestResult, last_values: Dict[str, Any]) -> None:
        step_type = step.get("type")

        if step_type == "measure":
            self._run_measure(step, result, last_values)

        elif step_type == "loop":
            count = int(step.get("count", 1))
            body = step.get("body", [])
            for _ in range(count):
                self._run_steps(body, result, last_values)

        elif step_type == "branch":
            if self._condition_true(step.get("condition"), last_values):
                self._run_steps(step.get("then", []), result, last_values)
            else:
                self._run_steps(step.get("else", []), result, last_values)

        else:
            raise ValueError("未知步骤类型: %r" % step_type)

    def _run_measure(self, step: Dict[str, Any], result: TestResult, last_values: Dict[str, Any]) -> None:
        instrument_id = step.get("instrument")
        instrument = self.instruments.get(instrument_id)
        if instrument is None:
            raise KeyError("流程引用了未配置的仪器: %r" % instrument_id)

        method = get_method(step.get("method"))
        measurement = method(instrument, step.get("params", {}))
        if not measurement.instrument_id:
            measurement.instrument_id = instrument_id

        result.measurements.append(measurement)
        if measurement.name:
            last_values[measurement.name] = measurement.value if measurement.value is not None else measurement.raw_value

    @staticmethod
    def _condition_true(condition: Optional[Dict[str, Any]], last_values: Dict[str, Any]) -> bool:
        if not condition:
            return True
        left = condition.get("left")
        right = condition.get("right")
        op = condition.get("op", "==")
        actual = last_values.get(left)
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
