"""
学生事务模块的 Module API。

其他模块（例如员工模块）如果需要“审批请假 / 录入成绩”，
只能通过这里调用，不能直接改 student 的表。
"""

from __future__ import annotations

from app.student.internal.service import (
    approve_leave,
    enroll_course,
    create_feedback,
    create_leave,
    list_feedback,
    list_leaves,
    list_scores,
    record_score,
    resolve_feedback,
)

__all__ = [
    "create_leave",
    "list_leaves",
    "approve_leave",
    "create_feedback",
    "list_feedback",
    "resolve_feedback",
    "record_score",
    "list_scores",
    "enroll_course",
]
