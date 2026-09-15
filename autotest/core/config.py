"""配置加载：应用配置与测试流程定义。"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

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
