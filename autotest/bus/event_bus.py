"""分层事件总线（原理验证用）。

各层在关键执行点上报事件，架构台据此展示**真实**的调用链与命令日志。
设计约束：
  - 纯标准库实现，**不依赖 PySide6**（HAL/核心层与无界面测试都能用）；
  - 上报失败绝不影响主流程（内部 try/except 吞掉异常）；
  - 线程安全：流程在后台线程执行，UI 在主线程读取；
  - 支持"噪声上下文"：周期性轮询（波形/读数）只计数不存储，避免淹没关键日志。
"""
from __future__ import annotations

import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

# 层标识（与设计文档一致）
LAYERS = ("ui", "glue", "app", "hal", "data", "report")

_MAX_DETAIL = 200


def _now() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def _short(value: Any, limit: int = _MAX_DETAIL) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r", " ").replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 3] + "..."


@dataclass
class LayerEvent:
    """一条分层事件。"""

    ts: str
    layer: str
    kind: str
    action: str
    detail: str = ""
    result: str = ""
    duration_ms: float = 0.0
    status: str = "ok"          # ok / error / skip
    source: str = ""            # sim / real
    corr_id: str = ""           # 关联同一次测试

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EventBus:
    """事件总线：环形缓冲 + 订阅分发 + 统计。"""

    def __init__(self, capacity: int = 500):
        self._capacity = int(capacity)
        self._events: deque = deque(maxlen=self._capacity)
        self._subs: List[Callable[[Dict[str, Any]], None]] = []
        self._lock = threading.RLock()
        self._local = threading.local()
        self._stats: Dict[str, int] = {layer: 0 for layer in LAYERS}
        self._total = 0
        self._noisy_total = 0

    # ---------- 线程本地上下文 ----------
    def set_correlation(self, corr_id: str) -> None:
        self._local.corr_id = corr_id

    def correlation(self) -> str:
        return getattr(self._local, "corr_id", "")

    def set_source(self, source: str) -> None:
        self._local.source = source

    def source(self) -> str:
        return getattr(self._local, "source", "")

    @contextmanager
    def context(self, corr_id: Optional[str] = None, source: Optional[str] = None):
        """一次性设置关联号/数据源（线程本地），退出时恢复。"""
        prev_corr = self.correlation()
        prev_source = self.source()
        if corr_id is not None:
            self.set_correlation(corr_id)
        if source is not None:
            self.set_source(source)
        try:
            yield self
        finally:
            self._local.corr_id = prev_corr
            self._local.source = prev_source

    @contextmanager
    def quiet(self):
        """噪声上下文：其中的事件只统计、不入缓冲、不通知界面。"""
        prev = getattr(self._local, "noisy", False)
        self._local.noisy = True
        try:
            yield self
        finally:
            self._local.noisy = prev

    def is_noisy(self) -> bool:
        return bool(getattr(self._local, "noisy", False))

    # ---------- 发布 ----------
    def publish(
        self,
        layer: str,
        kind: str,
        action: str,
        detail: Any = "",
        result: Any = "",
        duration_ms: float = 0.0,
        status: str = "ok",
        source: Optional[str] = None,
        corr_id: Optional[str] = None,
    ) -> None:
        """发布一条事件。任何异常都被吞掉，保证不影响被测流程。"""
        try:
            event = LayerEvent(
                ts=_now(),
                layer=layer,
                kind=kind,
                action=_short(action, 60),
                detail=_short(detail),
                result=_short(result),
                duration_ms=round(float(duration_ms), 3),
                status=status,
                source=source if source is not None else self.source(),
                corr_id=corr_id if corr_id is not None else self.correlation(),
            )
            noisy = self.is_noisy()
            with self._lock:
                self._total += 1
                self._stats[layer] = self._stats.get(layer, 0) + 1
                if noisy:
                    self._noisy_total += 1
                else:
                    self._events.append(event)
                subs = list(self._subs)
            if noisy:
                return
            payload = event.to_dict()
            for fn in subs:
                try:
                    fn(payload)
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001
            pass

    @contextmanager
    def span(
        self,
        layer: str,
        kind: str,
        action: str,
        detail: Any = "",
        source: Optional[str] = None,
        corr_id: Optional[str] = None,
        info: Optional[Dict[str, Any]] = None,
    ):
        """记录一段操作的耗时与结果。

        info 是调用方传入的可变字典，可在块内写入 info["result"] / info["status"]。
        """
        start = time.perf_counter()
        status = "ok"
        error = ""
        try:
            yield info if info is not None else {}
        except Exception as exc:  # noqa: BLE001
            status = "error"
            error = "%s: %s" % (type(exc).__name__, exc)
            raise
        finally:
            data = info or {}
            self.publish(
                layer=layer,
                kind=kind,
                action=action,
                detail=detail,
                result=error or data.get("result", ""),
                duration_ms=(time.perf_counter() - start) * 1000.0,
                status=str(data.get("status", status)),
                source=source,
                corr_id=corr_id,
            )

    # ---------- 订阅 / 查询 ----------
    def subscribe(self, fn: Callable[[Dict[str, Any]], None]) -> Callable[[], None]:
        with self._lock:
            self._subs.append(fn)

        def unsubscribe() -> None:
            with self._lock:
                if fn in self._subs:
                    self._subs.remove(fn)

        return unsubscribe

    def snapshot(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            items = [e.to_dict() for e in self._events]
        if limit is not None:
            return items[-int(limit):]
        return items

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total": self._total,
                "noisy": self._noisy_total,
                "stored": len(self._events),
                "capacity": self._capacity,
                "by_layer": dict(self._stats),
            }


# 模块级单例：各层直接 import 使用
bus = EventBus()


def get_bus() -> EventBus:
    return bus


def trace(layer: str, kind: str, action: str, **kwargs) -> None:
    bus.publish(layer, kind, action, **kwargs)


def span(layer: str, kind: str, action: str, **kwargs):
    return bus.span(layer, kind, action, **kwargs)
