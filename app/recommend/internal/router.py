"""
画像研判与推荐模块的 Router（Controller 层）。

只负责 HTTP 入参 / 出参。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.recommend.schemas import RecommendRequest, RecommendResponse

from .service import recommend

router = APIRouter()


@router.post(
    "",
    response_model=RecommendResponse,
    summary="根据用户描述推荐留学项目",
)
def recommend_api(payload: RecommendRequest) -> dict:
    """POST /api/recommend"""
    return recommend(payload)
