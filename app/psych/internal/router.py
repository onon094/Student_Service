"""
心理关怀模块的 Router（Controller 层）。

只负责 HTTP 入参 / 出参。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.shared.deps import (
    assert_self_or_staff,
    force_self_id,
    get_current_user,
    require_staff,
    scope_student_id,
)

from app.psych.schemas import (
    AlertOut,
    AlertUpdate,
    ConversationCreate,
    ConversationOut,
    EmotionAssessRequest,
    EmotionAssessResponse,
    ProfileOut,
)

from .service import (
    assess_emotion,
    get_profile,
    list_alerts,
    list_conversations,
    log_conversation,
    update_alert,
)

router = APIRouter()


@router.post(
    "/assess",
    response_model=EmotionAssessResponse,
    summary="评估学生情绪并触发预警",
)
def assess_emotion_api(payload: EmotionAssessRequest, user: dict = Depends(get_current_user)) -> dict:
    """POST /api/psych/assess（学生只能给自己记录情绪）"""
    payload = payload.model_copy(update={"student_id": force_self_id(user, payload.student_id)})
    return assess_emotion(payload)


@router.get(
    "/profile/{student_id}",
    response_model=ProfileOut,
    summary="查心理画像",
)
def get_profile_api(student_id: int, user: dict = Depends(get_current_user)) -> dict:
    """GET /api/psych/profile/1（学生只能看自己）"""
    assert_self_or_staff(user, student_id)
    return get_profile(student_id)


@router.get(
    "/alerts",
    response_model=list[AlertOut],
    summary="查心理预警列表",
)
def list_alerts_api(
    alert_status: str | None = Query(None, alias="status", description="未处理/跟进中/已解除"),
    user: dict = Depends(require_staff),
) -> list[dict]:
    """GET /api/psych/alerts?status=未处理（仅员工/管理员）"""
    return list_alerts(alert_status)


@router.patch(
    "/alerts/{alert_id}",
    response_model=AlertOut,
    summary="更新预警处理状态",
)
def update_alert_api(
    alert_id: int,
    payload: AlertUpdate,
    user: dict = Depends(require_staff),
) -> dict:
    """PATCH /api/psych/alerts/1（仅员工/管理员）"""
    return update_alert(alert_id, payload)


@router.post(
    "/conversations",
    response_model=ConversationOut,
    status_code=status.HTTP_201_CREATED,
    summary="写一条对话记录",
)
def log_conversation_api(payload: ConversationCreate, user: dict = Depends(get_current_user)) -> dict:
    """POST /api/psych/conversations（记录归属当前用户）"""
    payload = payload.model_copy(update={"user_id": force_self_id(user, payload.user_id)})
    return log_conversation(payload)


@router.get(
    "/conversations",
    response_model=list[ConversationOut],
    summary="查对话记录（学生看自己，员工可查任意用户）",
)
def list_conversations_api(
    user_id: int | None = Query(
        None,
        description="用户编号；学生传什么都只看自己，员工/管理员不传则看自己",
    ),
    limit: int = Query(50, ge=1, le=200, description="最多返回条数，默认 50"),
    user: dict = Depends(get_current_user),
) -> list[dict]:
    """GET /api/psych/conversations?user_id=1&limit=50"""
    # scope_student_id：学生强制返回自己的 uid，员工/管理员按传入值（None→自己）
    target_id = scope_student_id(user, user_id) or int(user["uid"])
    return list_conversations(int(target_id), limit)
