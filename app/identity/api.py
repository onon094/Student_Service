"""
身份模块的 Module API（模块公开接口）。

其他模块只能 import 这个文件，不能直接 import internal/。
它只做一层薄封装，真正的业务逻辑在 internal/service.py。
"""

from __future__ import annotations

from app.identity.internal.service import (
    create_student,
    login,
    ensure_employee,
    ensure_student,
    get_user,
    get_users_by_ids,
    list_employees,
    list_students,
)

__all__ = [
    "get_user",
    "get_users_by_ids",
    "list_students",
    "list_employees",
    "ensure_student",
    "ensure_employee",
    "create_student",
    "login",
]
