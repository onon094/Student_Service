"""
身份模块的 Router（Controller 层）。

职责：接收 HTTP 请求、调用 Service、返回响应。
不写业务规则，不直接操作数据库。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.identity.schemas import LoginRequest, LoginResponse, UserOut
from app.shared.deps import get_current_user, require_staff

from .service import get_user, list_employees, list_students, login

router = APIRouter()


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="账号密码登录（成功后签发令牌）",
)
def login_api(payload: LoginRequest) -> dict:
    """POST /api/identity/login"""
    return login(payload)


@router.get(
    "/users/{user_id}",
    response_model=UserOut,
    summary="按编号查用户",
)
def get_user_api(user_id: int, user: dict = Depends(get_current_user)) -> dict:
    """GET /api/identity/users/{user_id}（需登录；学生只能查自己）"""
    if user.get("role") == "student" and int(user["uid"]) != int(user_id):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="只能查看自己的信息")
    return get_user(user_id)


@router.get(
    "/students",
    response_model=list[UserOut],
    summary="查学生列表",
)
def list_students_api(user: dict = Depends(require_staff)) -> list[dict]:
    """GET /api/identity/students"""
    return list_students()


@router.get(
    "/employees",
    response_model=list[UserOut],
    summary="查员工列表",
)
def list_employees_api(department: str | None = None, user: dict = Depends(require_staff)) -> list[dict]:
    """GET /api/identity/employees?department=销售部"""
    return list_employees(department)
