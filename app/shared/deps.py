"""
请求上下文与权限依赖
================================================
认证（你是谁）由 main.py 的中间件统一完成，结果放在 request.state.user；
授权（你能不能做这件事）用这里的 Depends 在端点里声明。

角色取值与前端一致：
- student：学生，只能看自己的数据
- employee：员工 / 老师（老师已合并进员工）
- admin：开发管理员
- service：Dify 自定义工具用的服务账号（等同管理员，但不属于任何自然人）
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

# Dify 调用后端时的公开端点：投递官网表单、推荐、登录、健康检查（不分方法）
_PUBLIC_EXACT = {
    "/api/health",
    "/api/identity/login",
    "/api/recommend",
}
# 只放行 GET 的公开读接口：课程/活动的「新增」等写操作必须走登录鉴权。
# 坑：早期把这两条放进 _PUBLIC_EXACT 导致不区分方法，POST 新增会被匿名放行。
_PUBLIC_GET_ONLY = {
    "/api/catalog/projects",
    "/api/catalog/events",
}
_PUBLIC_PREFIXES = ("/docs", "/redoc", "/openapi.json", "/openapi-dify.json")


def is_public(method: str, path: str) -> bool:
    """判断某个请求是否可以匿名访问。"""
    if path in _PUBLIC_EXACT:
        return True
    # 课程 / 活动：仅 GET 公开，POST 新增要登录（require_staff 再判角色）
    if method == "GET" and path in _PUBLIC_GET_ONLY:
        return True
    if path.startswith(_PUBLIC_PREFIXES):
        return True
    # 官网获客表单：访客没有账号，必须允许匿名投递（只能创建，不能读取）
    if method == "POST" and path == "/api/employee/leads":
        return True
    # 官网展示用的单个项目详情
    if method == "GET" and path.startswith("/api/catalog/projects/"):
        return True
    return False


def get_current_user(request: Request) -> dict:
    """取当前登录用户；中间件没塞进 state 就视为未登录。"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_staff(user: dict = Depends(get_current_user)) -> dict:
    """员工 / 老师 / 管理员可访问。"""
    if user.get("role") not in ("employee", "admin"):
        raise HTTPException(status_code=403, detail="该操作需要员工权限")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """仅管理员。"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="该操作需要管理员权限")
    return user


def require_student(user: dict = Depends(get_current_user)) -> dict:
    """仅学生本人。"""
    if user.get("role") != "student":
        raise HTTPException(status_code=403, detail="该操作需要学生账号")
    return user


def scope_student_id(user: dict, requested_id: int | None) -> int | None:
    """
    列表查询的数据范围：
    - 学生：无论传什么，都只查自己；
    - 员工/管理员：按传入值查，None 表示查全部（后台列表）。
    """
    if user.get("role") == "student":
        return int(user["uid"])
    return requested_id


def force_self_id(user: dict, declared_id: int) -> int:
    """
    写操作的主体：
    - 学生：一律以 token 里的 uid 为准，忽略请求体里的 student_id（防冒用）；
    - 员工/管理员：用请求体里的值（代学生提交）。
    """
    if user.get("role") == "student":
        return int(user["uid"])
    return int(declared_id)


def assert_self_or_staff(user: dict, target_id: int) -> None:
    """查看某个学生的数据：学生只能看自己，员工/管理员可看全部。"""
    if user.get("role") == "student" and int(user["uid"]) != int(target_id):
        raise HTTPException(status_code=403, detail="只能查看自己的数据")
