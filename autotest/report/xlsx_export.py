"""Excel 输出接口（预留，阶段5 仅保留接口）。

设计文档决策：现阶段仅输出 HTML；Excel 输出保留接口，待后续阶段实现。
实现时可选用：
  1) openpyxl（需 pip 安装）：直接写入 .xlsx，可完整保留合并单元格与边框样式；
  2) 自研写出（zipfile + XML）：零依赖，但样式支持有限。
调用 save_acceptance_xlsx() 时如未启用实现，将抛出 ExcelExportNotImplemented 并在界面提示。
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class ExcelExportNotImplemented(NotImplementedError):
    """Excel 输出尚未实现（接口已预留）。"""


def is_available() -> bool:
    """是否具备 Excel 输出能力（当前阶段恒为 False）。"""
    return False


def save_acceptance_xlsx(report: Dict[str, Any], path: str,
                         template: Optional[Dict[str, Any]] = None) -> str:
    """把验收记录表导出为 .xlsx（接口预留）。

    :param report:   acceptance.build_report() 的结果
    :param path:     目标 .xlsx 路径
    :param template: 报表模板（可选）
    :return: 实际写入路径
    :raises ExcelExportNotImplemented: 当前阶段未实现
    """
    raise ExcelExportNotImplemented(
        "Excel 输出接口已预留，当前阶段仅支持 HTML 输出（设计文档阶段5 决策）")
