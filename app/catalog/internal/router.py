"""
课程与活动模块的 Router（Controller 层）。

只负责 HTTP 入参 / 出参。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.shared.deps import get_current_user, require_staff

from app.catalog.schemas import (
    EventCreate,
    EventOut,
    ProjectCreate,
    ProjectOut,
    RegisterRequest,
    RegisterWithInfoOut,
    RegisterWithInfoRequest,
    RegistrationOut,
)

from .service import (
    cancel_registration,
    create_event,
    create_project,
    list_events,
    list_projects,
    list_registrations,
    register_event,
    register_with_info,
)

router = APIRouter()


@router.get(
    "/projects",
    response_model=list[ProjectOut],
    summary="查课程 / 项目",
)
def list_projects_api(
    keyword: str | None = Query(None, description="项目名或介绍关键词"),
    category: str | None = Query(None, description="国际本科/本硕连读/就业班/学历提升/德国项目"),
) -> list[dict]:
    """GET /api/catalog/projects?keyword=新加坡"""
    return list_projects(keyword, category)


@router.post(
    "/projects",
    response_model=ProjectOut,
    status_code=status.HTTP_201_CREATED,
    summary="新增课程 / 项目（仅员工，真人操作）",
)
def create_project_api(
    payload: ProjectCreate,
    user: dict = Depends(require_staff),
) -> dict:
    """POST /api/catalog/projects —— 新建项目，仅员工/管理员可调用。"""
    return create_project(payload)


@router.get(
    "/events",
    response_model=list[EventOut],
    summary="查活动列表",
)
def list_events_api(
    event_type: str | None = Query(None, description="线上 / 线下"),
) -> list[dict]:
    """GET /api/catalog/events?event_type=线上"""
    return list_events(event_type)


@router.post(
    "/events",
    response_model=EventOut,
    status_code=status.HTTP_201_CREATED,
    summary="新增活动（仅员工，真人操作）",
)
def create_event_api(
    payload: EventCreate,
    user: dict = Depends(require_staff),
) -> dict:
    """POST /api/catalog/events —— 新建活动，仅员工/管理员可调用。"""
    return create_event(payload)


@router.post(
    "/events/{event_id}/register",
    response_model=RegistrationOut,
    status_code=status.HTTP_201_CREATED,
    summary="活动报名",
)
def register_event_api(
    event_id: int,
    payload: RegisterRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    """POST /api/catalog/events/1/register"""
    return register_event(event_id, payload)


@router.post(
    "/events/{event_id}/register-with-info",
    response_model=RegisterWithInfoOut,
    status_code=status.HTTP_201_CREATED,
    summary="真实报名：带姓名电话一步建档+报名（Dify 客服助手用）",
)
def register_with_info_api(
    event_id: int,
    payload: RegisterWithInfoRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    """
    POST /api/catalog/events/1/register-with-info

    供 Dify 客服助手在对话里收集姓名电话后调用；真人/服务令牌均可。
    返回带真实姓名的播报数据，智能体据此如实回复。
    """
    return register_with_info(event_id, payload)


@router.get(
    "/my-registrations",
    response_model=list[RegistrationOut],
    summary="查我的报名记录（学生本人）",
)
def my_registrations_api(user: dict = Depends(get_current_user)) -> list[dict]:
    """GET /api/catalog/my-registrations"""
    return list_registrations(customer_id=int(user["uid"]))


@router.get(
    "/registrations",
    response_model=list[RegistrationOut],
    summary="查报名记录",
)
def list_registrations_api(
    event_id: int | None = Query(None, description="活动编号"),
    user: dict = Depends(require_staff),
) -> list[dict]:
    """GET /api/catalog/registrations?event_id=1（仅员工，含客户信息）"""
    return list_registrations(event_id)


@router.post(
    "/registrations/{registration_id}/cancel",
    response_model=RegistrationOut,
    summary="取消活动报名（软删除，回滚名额）",
)
def cancel_registration_api(
    registration_id: int,
    user: dict = Depends(get_current_user),
) -> dict:
    """POST /api/catalog/registrations/{registration_id}/cancel（登录用户，报名人或员工）"""
    return cancel_registration(registration_id)
