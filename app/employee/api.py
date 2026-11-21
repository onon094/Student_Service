"""
员工业务模块的 Module API。

其他模块如果需要“查客户线索 / 写日报”，只能走这里。
"""

from __future__ import annotations

from app.employee.internal.service import (
    create_lead,
    create_report,
    find_signed_lead,
    get_leads_by_ids,
    list_leads,
    list_reports,
    sign_lead,
    update_lead_status,
)

__all__ = [
    "create_lead",
    "list_leads",
    "get_leads_by_ids",
    "find_signed_lead",
    "update_lead_status",
    "create_report",
    "list_reports",
    "sign_lead",
]
