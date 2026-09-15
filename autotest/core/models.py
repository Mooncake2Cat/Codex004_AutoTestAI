"""核心域模型定义。

本模块定义与具体存储、通信、UI 无关的纯数据结构，供各层共享。
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="milliseconds")


@dataclass
class Measurement:
    """单次测量结果。"""

    name: str
    value: Optional[float] = None
    unit: str = ""
    instrument_id: str = ""
    raw_value: Any = None
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Measurement":
        return cls(
            name=data.get("name", ""),
            value=data.get("value"),
            unit=data.get("unit", ""),
            instrument_id=data.get("instrument_id", ""),
            raw_value=data.get("raw_value"),
            timestamp=data.get("timestamp", _now()),
        )


@dataclass
class TestResult:
    """一次测试流程运行的完整结果。"""

    # 防止 pytest 误把该类当作测试类收集（类名以 Test 开头）
    __test__ = False

    test_id: str
    dut_info: Dict[str, Any] = field(default_factory=dict)
    test_conditions: Dict[str, Any] = field(default_factory=dict)
    measurements: List[Measurement] = field(default_factory=list)
    status: str = "unknown"
    message: str = ""
    started_at: str = field(default_factory=_now)
    finished_at: Optional[str] = None

    def finish(self, status: str, message: str = "") -> None:
        self.status = status
        self.message = message
        self.finished_at = _now()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestResult":
        result = cls(
            test_id=data.get("test_id", ""),
            dut_info=data.get("dut_info", {}),
            test_conditions=data.get("test_conditions", {}),
            status=data.get("status", "unknown"),
            message=data.get("message", ""),
            started_at=data.get("started_at", _now()),
            finished_at=data.get("finished_at"),
        )
        result.measurements = [
            Measurement.from_dict(m) for m in data.get("measurements", [])
        ]
        return result

