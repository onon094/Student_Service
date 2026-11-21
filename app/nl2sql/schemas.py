"""NL2SQL 模块的公开数据结构（DTO）。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class NL2SQLRequest(BaseModel):
    """用户用口语描述要查什么。"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "查一下许同学的跟进记录",
            }
        }
    )

    question: str = Field(min_length=1, max_length=500)


class NL2SQLResponse(BaseModel):
    """NL2SQL 执行结果。"""

    sql: str
    columns: list[str] = []
    rows: list[dict] = []
    message: str = ""
    attempts: int = 0
    # llm = 大模型生成 SQL；fallback = 模型不可用时用预置查询降级
    source: str = "llm"
