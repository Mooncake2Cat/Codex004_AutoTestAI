"""波形计算 / 算法模块（一期）。

供流程 `compute` 步骤调用：输入来自测量值、常量或波形数组，输出命名变量，
供 `limit_check` / `report` 使用。纯标准库实现（不依赖 numpy）。

一期算法（按设计文档 §15 决策）：
  数学：add / sub / mul / div
  波形：vpp / vrms / vavg / duty / lowpass / fft_peak
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

# 算法声明（供流程编辑器自动列出）
ALGORITHMS: List[Dict[str, Any]] = [
    {"id": "add", "label": "相加 A+B", "params": ["a", "b"]},
    {"id": "sub", "label": "相减 A-B", "params": ["a", "b"]},
    {"id": "mul", "label": "相乘 A×B", "params": ["a", "b"]},
    {"id": "div", "label": "相除 A÷B", "params": ["a", "b"]},
    {"id": "vpp", "label": "峰峰值 Vpp", "params": ["values"]},
    {"id": "vrms", "label": "有效值 Vrms", "params": ["values"]},
    {"id": "vavg", "label": "平均值 Vavg", "params": ["values"]},
    {"id": "duty", "label": "占空比 Duty(%)", "params": ["values"]},
    {"id": "lowpass", "label": "一阶低通滤波", "params": ["values", "alpha"]},
    {"id": "fft_peak", "label": "FFT 峰值频率", "params": ["values", "sample_interval"]},
]

_IDS = {a["id"] for a in ALGORITHMS}


def list_algorithms() -> List[Dict[str, Any]]:
    return [dict(a) for a in ALGORITHMS]


def _numbers(values: Any) -> List[float]:
    if isinstance(values, (list, tuple)):
        return [float(v) for v in values if v is not None]
    if values is None:
        return []
    return [float(values)]


def compute(algorithm_id: str, inputs: Optional[Dict[str, Any]] = None,
            params: Optional[Dict[str, Any]] = None) -> Tuple[bool, Any, str]:
    """执行算法。返回 (ok, value, detail)。"""
    inputs = dict(inputs or {})
    params = dict(params or {})
    aid = str(algorithm_id)

    def get(name, default=None):
        if name in inputs:
            return inputs[name]
        return params.get(name, default)

    try:
        if aid == "add":
            return True, float(get("a", 0)) + float(get("b", 0)), "a+b"
        if aid == "sub":
            return True, float(get("a", 0)) - float(get("b", 0)), "a-b"
        if aid == "mul":
            return True, float(get("a", 0)) * float(get("b", 0)), "a*b"
        if aid == "div":
            b = float(get("b", 0))
            if b == 0:
                return False, None, "除数为 0"
            return True, float(get("a", 0)) / b, "a/b"

        values = _numbers(get("values"))
        if not values:
            return False, None, "输入数据为空"

        if aid == "vpp":
            return True, max(values) - min(values), "Vpp"
        if aid == "vrms":
            return True, math.sqrt(sum(v * v for v in values) / len(values)), "Vrms"
        if aid == "vavg":
            return True, sum(values) / len(values), "Vavg"
        if aid == "duty":
            mid = (max(values) + min(values)) / 2.0
            high = sum(1 for v in values if v > mid)
            return True, 100.0 * high / len(values), "Duty%"
        if aid == "lowpass":
            alpha = float(get("alpha", 0.2))
            out, prev = [], values[0]
            for v in values:
                prev = prev + alpha * (v - prev)
                out.append(prev)
            return True, out, "一阶低通(alpha=%.3f)" % alpha
        if aid == "fft_peak":
            dt = float(get("sample_interval", 1e-6)) or 1e-6
            n = min(len(values), 256)
            data = values[:n]
            mean = sum(data) / n
            mags: List[float] = [0.0] * (n // 2 + 2)
            best_k = 1
            for k in range(1, n // 2 + 1):
                re = im = 0.0
                for i, v in enumerate(data):
                    ang = 2.0 * math.pi * k * i / n
                    re += (v - mean) * math.cos(ang)
                    im -= (v - mean) * math.sin(ang)
                mags[k] = re * re + im * im
                if mags[k] > mags[best_k]:
                    best_k = k
            # 抛物线插值：用相邻三点修正峰值位置（显著提升频率分辨率）
            delta = 0.0
            if 1 < best_k < n // 2:
                m0, m1, m2 = mags[best_k - 1], mags[best_k], mags[best_k + 1]
                denom = (m0 - 2.0 * m1 + m2)
                if abs(denom) > 1e-20:
                    delta = 0.5 * (m0 - m2) / denom
                    delta = max(-0.5, min(0.5, delta))
            freq = (best_k + delta) / (n * dt)
            return True, freq, "FFT 峰值 k=%d(%.2f)" % (best_k, best_k + delta)

        return False, None, "未知算法: %s" % algorithm_id
    except Exception as exc:  # noqa: BLE001
        return False, None, "%s: %s" % (type(exc).__name__, exc)


def is_algorithm(algorithm_id: str) -> bool:
    return str(algorithm_id) in _IDS

