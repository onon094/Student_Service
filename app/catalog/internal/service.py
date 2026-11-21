"""
课程与活动模块的 Service（业务层）。

职责：
- 课程 / 项目查询；
- 活动查询；
- 活动报名：名额校验、防重复报名、报名人数 +1。
"""

from __future__ import annotations

from datetime import datetime

from app.catalog.schemas import (
    EventCreate,
    ProjectCreate,
    RegisterRequest,
    RegisterWithInfoRequest,
)
from app.shared.errors import BadRequestError, ConflictError, NotFoundError

from . import repository


def list_projects(keyword: str | None = None, category: str | None = None) -> list[dict]:
    """查课程 / 项目。"""
    return repository.list_projects(keyword, category)


def get_project(project_id: int) -> dict | None:
    """按 id 取课程项目，不存在返回 None（由调用方决定是否报 404）。"""
    return repository.get_project(project_id)


def create_project(payload: ProjectCreate) -> dict:
    """
    新增课程 / 项目。

    校验：名称不能是纯空白（Pydantic 的 min_length 只挡空串，挡不住"   "）。
    返回新建的完整记录，前端拿到 id 后可直接刷新列表。
    """
    name = (payload.project_name or "").strip()
    if not name:
        raise BadRequestError("项目名称不能为空")

    new_id = repository.create_project(
        project_name=name,
        category=payload.category,
        description=payload.description,
        target_audience=payload.target_audience,
    )
    return repository.get_project(new_id)


def list_events(event_type: str | None = None) -> list[dict]:
    """查活动列表。"""
    return repository.list_events(event_type)


def create_event(payload: EventCreate) -> dict:
    """
    新增活动 / 讲座。

    校验：
    1. 名称不能是纯空白；
    2. 开始时间要能解析（避免前台显示乱串），兼容常见的空格 / T 分隔；
    3. 人数在 Pydantic 已限制 >=1，这里不重复。
    """
    name = (payload.event_name or "").strip()
    if not name:
        raise BadRequestError("活动名称不能为空")

    start = (payload.start_time or "").strip()
    if start:
        # 允许 "2026-12-01 14:00" / "...14:00:00" / ISO 的 T 分隔
        normalized = start.replace("T", " ")
        try:
            parsed = datetime.strptime(normalized[:16], "%Y-%m-%d %H:%M")
        except ValueError:
            raise BadRequestError("开始时间格式应为 年-月-日 时:分，例如 2026-12-01 14:00")
        # 统一存成 "年-月-日 时:分:秒"，避免前端显示成 ISO 的 T 分隔
        start = parsed.strftime("%Y-%m-%d %H:%M:%S")

    new_id = repository.create_event(
        event_name=name,
        event_type=payload.event_type,
        start_time=start,
        location=payload.location,
        max_participants=payload.max_participants,
        current_participants=payload.current_participants or 0,
    )
    return repository.get_event(new_id)


def register_event(event_id: int, payload: RegisterRequest) -> dict:
    """
    活动报名。

    1. 活动必须存在；
    2. 名额不能满；
    3. 同一个客户不能重复报名；
    4. 报名记录 + 活动人数 +1 在同一事务里完成。

    说明：customer_id 来自 crm_lead（客户线索表）。
    本期不做强校验，由 Dify / 前端保证传的是有效客户。
    """
    event = repository.get_event(event_id)
    if not event:
        raise NotFoundError(f"活动 {event_id} 不存在")

    # 说明：customer_id 来自 crm_lead。课程模块不反向依赖员工模块，
    # 所以这里不做客户存在性校验（由报名方保证传入有效 id）。
    current = event.get("current_participants") or 0
    maximum = event.get("max_participants")
    if maximum is not None and current >= maximum:
        raise BadRequestError(f"活动 {event_id} 名额已满")

    existing = repository.find_registration(event_id, payload.customer_id)
    if existing:
        raise ConflictError(f"客户 {payload.customer_id} 已经报名活动 {event_id}")

    registration_id = repository.create_registration(event_id, payload.customer_id)
    registration = repository.get_registration(registration_id)
    # 修复：原代码调用不存在的 _enrich_registrations，导致报名写库成功却返回 500。
    # 与 list_registrations 口径保持一致：只返回本模块字段，客户姓名由前端补。
    return registration


def register_with_info(event_id: int, payload: RegisterWithInfoRequest) -> dict:
    """
    聚合报名：先建客户线索，再用新客户 id 报名，一步完成。

    校验顺序（先校验再写库，避免校验失败留下脏数据）：
    1. 姓名不能是纯空白；
    2. 活动必须存在；
    3. 名额不能满。
    真实姓名会被带回出参，让智能体照着播报，不再张冠李戴。
    """
    name = (payload.customer_name or "").strip()
    if not name:
        raise BadRequestError("客户姓名不能为空")

    event = repository.get_event(event_id)
    if not event:
        raise NotFoundError(f"活动 {event_id} 不存在")

    current = event.get("current_participants") or 0
    maximum = event.get("max_participants")
    if maximum is not None and current >= maximum:
        raise BadRequestError(f"活动 {event_id} 名额已满")

    # 建客户 + 报名 + 人数+1 在同一事务；owner 用陈老师(7)作为演示环境负责人
    result = repository.register_with_info(
        event_id=event_id,
        customer_name=name,
        contact_info=(payload.contact_info or "").strip() or None,
        background_info=(payload.background_info or "").strip() or None,
        owner_employee_id=7,
    )
    return {
        "success": True,
        "registration_id": result["id"],
        "customer_id": result["customer_id"],
        "customer_name": name,
        "event_id": event_id,
        "event_name": event.get("event_name"),
        "status": result["status"],
        "message": f"{name} 已成功报名活动「{event.get('event_name')}」，报名编号 {result['id']}",
    }


def list_registrations(event_id: int | None = None, customer_id: int | None = None) -> list[dict]:
    """
    查报名记录。

    只返回本模块的数据（event_id / customer_id / status / 时间）。
    客户姓名由调用方（前端）用客户线索接口补，避免课程模块反向依赖员工模块。
    """
    return repository.list_registrations(event_id, customer_id)


def cancel_registration(registration_id: int) -> dict:
    """
    取消报名（软删除）。

    1. 记录不存在 → 404；
    2. 已是「已取消」→ 409，明确告诉调用方不要重复取消；
    3. 正常取消 → 状态改「已取消」+ 活动人数 -1，返回最新记录。

    软删除而非物理删除：保留报名历史，且和前端 status !== '已取消' 的过滤口径一致。
    """
    registration = repository.get_registration(registration_id)
    if not registration:
        raise NotFoundError(f"报名记录 {registration_id} 不存在")
    if registration["status"] == "已取消":
        raise ConflictError(f"报名记录 {registration_id} 已经取消，请勿重复操作")

    repository.cancel_registration(registration_id)
    return repository.get_registration(registration_id)
