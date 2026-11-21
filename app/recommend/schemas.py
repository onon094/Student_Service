"""画像研判与推荐模块的公开数据结构（DTO）。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RecommendRequest(BaseModel):
    """推荐入参：raw_text 必填，structured 可选（大模型已抽好的字段）。"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "raw_text": "19岁高中刚毕业，想快点拿本科学历",
            }
        }
    )

    raw_text: str = Field(min_length=1, max_length=1000)
    structured: dict | None = None
    name: str | None = None


class MatchItem(BaseModel):
    """一个推荐项目 + 理由 + 匹配度。"""

    project_id: int
    project_name: str
    category: str | None = None
    reason: str
    score: int


class RecommendResponse(BaseModel):
    """推荐结果。"""

    profile: dict
    matches: list[MatchItem]
    best_match: MatchItem | None = None
    summary: str
