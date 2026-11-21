"""
领域异常模块
------------
Service 层只抛业务异常，不依赖 FastAPI 的 HTTPException。
main.py 统一把这些异常翻译成 HTTP 状态码，保证分层干净。
"""

from __future__ import annotations


class DomainError(Exception):
    """所有业务异常的基类：默认 400。"""

    status_code = 400
    code = "bad_request"

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class BadRequestError(DomainError):
    """参数不合法、业务前置条件不满足：400。"""

    status_code = 400
    code = "bad_request"


class NotFoundError(DomainError):
    """资源或关联记录不存在：404。"""

    status_code = 404
    code = "not_found"


class ConflictError(DomainError):
    """唯一性冲突、状态冲突：409。"""

    status_code = 409
    code = "conflict"


class UnprocessableError(DomainError):
    """数据校验失败：422。"""

    status_code = 422
    code = "unprocessable"


class UnauthorizedError(DomainError):
    """账号或密码不正确、令牌无效：401。"""

    status_code = 401
    code = "unauthorized"


class ForbiddenError(DomainError):
    """已登录但权限不足：403。"""

    status_code = 403
    code = "forbidden"
