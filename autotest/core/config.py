"""配置加载：应用配置与测试流程定义。"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def resolve_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(PROJECT_ROOT, path))


def load_app_config(path: str = "config/app_config.json") -> Dict[str, Any]:
    return load_json(resolve_path(path))


def load_flow(path: str) -> Dict[str, Any]:
    return load_json(resolve_path(path))


def load_instruments(path: str = "config/instruments.json") -> List[Dict[str, Any]]:
    """加载仪器注册表（含能力声明、传输参数、面板名、可见性）。

    注册表是"多仪器/多协议"扩展的唯一入口：新增仪器只需在此追加一条，
    界面（仪器坞）与流程编辑会自动出现该仪器。
    """
    try:
        data = load_json(resolve_path(path))
    except FileNotFoundError:
        return []
    return list(data.get("instruments", []))

