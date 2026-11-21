"""
身份模块的 Service（业务层）。

职责：
- 判断用户是否存在；
- 判断用户是不是学生 / 员工；
- 给其他模块提供“确认身份”的能力。
"""

from __future__ import annotations

import time

from app.identity.schemas import LoginRequest
from app.shared.config import TOKEN_TTL_HOURS
from app.shared.errors import BadRequestError, ForbiddenError, NotFoundError, UnauthorizedError
from app.shared.security import create_token, verify_password

from . import repository


def get_user(user_id: int) -> dict:
    """按 id 查用户，不存在抛 404。"""
    user = repository.get_user(user_id)
    if not user:
        raise NotFoundError(f"用户 {user_id} 不存在")
    return user


def get_users_by_ids(user_ids: list[int]) -> list[dict]:
    """批量查用户，供其他模块补姓名。"""
    return repository.get_users_by_ids(user_ids)


def list_students() -> list[dict]:
    """查所有学生。"""
    return repository.list_users(user_type="STUDENT")


def list_employees(department: str | None = None) -> list[dict]:
    """按部门查员工；不传部门则查全部员工。"""
    return repository.list_users(user_type="EMPLOYEE", department=department)


def ensure_student(user_id: int) -> dict:
    """
    确认 user_id 是一个有效的学生。

    其他模块在“给这个学生办业务”之前调用，
    避免把请假、成绩等数据挂到不存在或非学生的账号上。
    """
    user = get_user(user_id)
    if user["user_type"] != "STUDENT":
        raise BadRequestError(f"用户 {user_id} 不是学生")
    if user["status"] != "正常":
        raise BadRequestError(f"学生 {user_id} 账号状态为 {user['status']}，不能办理业务")
    return user


def ensure_employee(user_id: int) -> dict:
    """确认 user_id 是一个有效的员工（审批人 / 负责人）。"""
    user = get_user(user_id)
    if user["user_type"] != "EMPLOYEE":
        raise BadRequestError(f"用户 {user_id} 不是员工")
    if user["status"] != "正常":
        raise BadRequestError(f"员工 {user_id} 账号状态为 {user['status']}，不能办理业务")
    return user


def create_student(
    real_name: str,
    username: str | None = None,
    department: str | None = None,
    contact_info: str | None = None,
    password_hash: str = "hash",
) -> dict:
    """
    创建一个学生账号，返回学生信息。

    业务契约：**签约之后才建账号**——未签约的人只是意向客户，
    不应该出现在学生名单里。所以这个方法只由「签约」流程调用。

    username 为空时按 student_<时间戳> 兜底；重名自动加序号，
    避免两个同名学生互相覆盖。
    """
    name = (real_name or "").strip()
    if not name:
        raise BadRequestError("学生姓名不能为空")

    base = (username or "").strip() or f"student_{int(time.time()) % 1000000}"
    final = base
    index = 1
    while repository.get_user_by_username(final):
        index += 1
        final = f"{base}{index}"

    user_id = repository.create_user(
        username=final,
        password_hash=password_hash,
        real_name=name,
        user_type="STUDENT",
        department=department,
        contact_info=contact_info,
    )
    return get_user(user_id)


def role_of_user(user: dict) -> str:
    """
    把数据库里的用户翻译成前端使用的角色。

    学生 → student；员工里 employee_role=管理员 → admin；其余员工（含班主任）→ employee。
    老师已合并进员工，这里不再单独返回 teacher。
    """
    if user.get("user_type") == "STUDENT":
        return "student"
    if user.get("employee_role") == "管理员":
        return "admin"
    return "employee"


def login(payload: LoginRequest) -> dict:
    """
    账号密码登录，成功后签发令牌。

    安全约定：
    - 账号不存在与密码错误返回同一句提示，避免枚举账号；
    - 被禁用的账号单独提示 403；
    - 令牌里只放 uid / role / username，不放手机号等个人信息。
    """
    username = (payload.username or "").strip()
    user = repository.get_user_by_username(username)

    if not user or not verify_password(payload.password, user.get("password_hash") or ""):
        raise UnauthorizedError("账号或密码不正确")

    if user.get("status") != "正常":
        raise ForbiddenError("该账号已被禁用，请联系管理员")

    role = role_of_user(user)
    token = create_token(uid=int(user["id"]), role=role, username=user["username"])

    return {
        "token": token,
        "expires_in": TOKEN_TTL_HOURS * 3600,
        "user": user,
        "role": role,
    }
