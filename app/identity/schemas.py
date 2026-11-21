"""身份模块的公开数据结构（DTO）。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    """返回给外部的用户信息；不包含 password_hash。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    real_name: str
    user_type: str
    employee_role: str | None = None
    department: str | None = None
    contact_info: str | None = None
    status: str


class LoginRequest(BaseModel):
    """登录入参。"""

    model_config = ConfigDict(
        json_schema_extra={"example": {"username": "student_zhang", "password": "123456"}}
    )

    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=100)


class LoginResponse(BaseModel):
    """登录结果：令牌 + 用户信息 + 角色。"""

    token: str
    expires_in: int
    user: UserOut
    role: str
