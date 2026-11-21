"""心理关怀模块的公开数据结构（DTO）。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EmotionAssessRequest(BaseModel):
    """
    情绪评估入参。

    手工测试只填 student_id + text 即可。
    emotion_tag / emotion_score 是给大模型（Dify）传结果用的；
    如果不填，后端会用关键词兜底。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "student_id": 1,
                "text": "最近压力好大，感觉活不下去了",
            }
        }
    )

    student_id: int
    text: str = Field(min_length=1, max_length=2000)
    emotion_tag: str | None = None
    emotion_score: int | None = Field(default=None, ge=0, le=100)


class EmotionAssessResponse(BaseModel):
    """情绪评估结果。"""

    student_id: int
    emotion_tag: str
    emotion_score: int
    risk_level: str
    alerted: bool
    alert_id: int | None = None
    message: str


class ProfileOut(BaseModel):
    """心理画像。"""

    student_id: int
    latest_emotion_tag: str | None = None
    emotion_score: int | None = None
    last_interaction_time: str | None = None
    emotion_history: list[dict] = []


class AlertOut(BaseModel):
    """心理预警记录；带 student_name，后台列表不用再拿 id 猜人。"""

    id: int
    student_id: int
    student_name: str | None = None
    trigger_reason: str
    risk_level: str
    status: str
    teacher_id: int | None = None
    teacher_name: str | None = None
    create_time: str | None = None


class AlertUpdate(BaseModel):
    """更新预警处理状态。"""

    status: Literal["未处理", "跟进中", "已解除"]
    teacher_id: int | None = None


class ConversationCreate(BaseModel):
    """写一条对话记录。"""

    user_id: int
    agent_type: str
    user_input: str
    ai_output: str | None = None
    emotion_tag: str | None = None


class ConversationOut(BaseModel):
    """对话记录。"""

    id: int
    user_id: int
    agent_type: str
    user_input: str
    ai_output: str | None = None
    emotion_tag: str | None = None
    create_time: str | None = None
