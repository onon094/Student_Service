"""
课程与活动模块的 Module API。

recommend 模块需要读课程 / 项目数据，只能通过这里调用。
"""

from __future__ import annotations

from app.catalog.internal.service import (
    get_project,
    list_events,
    list_projects,
    list_registrations,
    register_event,
)

__all__ = [
    "list_projects",
    "get_project",
    "list_events",
    "register_event",
    "list_registrations",
]
