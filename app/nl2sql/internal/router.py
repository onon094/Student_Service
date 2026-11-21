"""
NL2SQL 模块的 Router（Controller 层）。

只负责 HTTP 入参 / 出参。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.nl2sql.schemas import NL2SQLRequest, NL2SQLResponse
from app.shared.deps import require_staff

from .service import query

router = APIRouter()


@router.post(
    "/query",
    response_model=NL2SQLResponse,
    summary="用自然语言查询数据库（只读）",
)
def query_api(payload: NL2SQLRequest, user: dict = Depends(require_staff)) -> dict:
    """POST /api/nl2sql/query"""
    return query(payload)
