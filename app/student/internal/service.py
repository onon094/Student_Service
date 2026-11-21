"""
学生事务模块的 Service（业务层）。

职责：
- 请假：校验学生、解析时间、状态流转；
- 售后：工单创建 / 查询 / 解决；
- 成绩：录入 / 查询。

跨模块调用只走 app.identity.api，不直接查 sys_user 表。
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from app.catalog import api as catalog_api
from app.identity import api as identity_api
from app.shared.errors import BadRequestError, ConflictError, NotFoundError
from app.student.schemas import (
    EnrollmentCreate,
    FeedbackCreate,
    LeaveCreate,
    ScoreCreate,
    ScoreUpdate,
)

from . import repository


# ============================================================
# 请假
# ============================================================
def _format_time(value: datetime) -> str:
    """把 datetime 转成 SQLite 习惯的字符串格式。"""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def parse_leave_time(reason: str, now: datetime | None = None) -> tuple[str, str]:
    """
    从请假事由里解析起止时间。

    支持：
    - 今天 / 明天 / 后天
    - 2026-12-01 / 12月1日
    - 半天 / 一天 / 两天 / 三天

    解析不出来时默认“明天 09:00 ~ 18:00”。
    这是规则兜底；以后也可以改成让大模型抽取。
    """
    current = now or datetime.now()
    text = reason or ""

    # 先确定是哪一天
    base = current.replace(hour=9, minute=0, second=0, microsecond=0)

    if "后天" in text:
        base += timedelta(days=2)
    elif "明天" in text:
        base += timedelta(days=1)
    elif "今天" in text or "今日" in text:
        pass
    else:
        # 2026-12-01 或 2026/12/01
        matched = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
        if matched:
            year, month, day = (int(part) for part in matched.groups())
            base = base.replace(year=year, month=month, day=day)
        else:
            # 12月1日
            matched = re.search(r"(\d{1,2})月(\d{1,2})[日号]", text)
            if matched:
                month, day = (int(part) for part in matched.groups())
                base = base.replace(month=month, day=day)
            else:
                # 没说日期，默认明天
                base += timedelta(days=1)

    # 再确定时长
    start = base

    if "半天" in text:
        end = base.replace(hour=12, minute=0, second=0)
    elif "三天" in text:
        end = (base + timedelta(days=3)).replace(hour=18, minute=0, second=0)
    elif "两天" in text:
        end = (base + timedelta(days=2)).replace(hour=18, minute=0, second=0)
    else:
        end = base.replace(hour=18, minute=0, second=0)

    return _format_time(start), _format_time(end)


def _attach_names(rows: list[dict]) -> list[dict]:
    """
    给请假记录补“学生姓名”和“审批人姓名”。

    通过 identity.api 批量取，不直接查 sys_user 表，也避免 N+1。
    """
    related_ids: set[int] = set()
    for row in rows:
        if row.get("student_id") is not None:
            related_ids.add(row["student_id"])
        if row.get("approver_id") is not None:
            related_ids.add(row["approver_id"])

    users = identity_api.get_users_by_ids(sorted(related_ids))
    name_map = {user["id"]: user["real_name"] for user in users}

    for row in rows:
        row["student_name"] = name_map.get(row.get("student_id"))
        row["approver_name"] = name_map.get(row.get("approver_id"))

    return rows


def get_leave(leave_id: int) -> dict:
    """按 id 查请假记录，不存在抛 404。"""
    leave = repository.get_leave(leave_id)
    if not leave:
        raise NotFoundError(f"请假记录 {leave_id} 不存在")
    return _attach_names([leave])[0]


def create_leave(payload: LeaveCreate) -> dict:
    """
    提交请假申请。

    1. 先确认学生存在且状态正常；
    2. 没传起止时间时，从 reason 里解析；
    3. 写入后返回完整记录。
    """
    identity_api.ensure_student(payload.student_id)

    if payload.start_time and payload.end_time:
        start = _format_time(payload.start_time)
        end = _format_time(payload.end_time)
    else:
        start, end = parse_leave_time(payload.reason)

    leave_id = repository.create_leave(
        student_id=payload.student_id,
        service_type=payload.service_type,
        start_time=start,
        end_time=end,
        reason=payload.reason,
    )
    return get_leave(leave_id)


def list_leaves(
    student_id: int | None = None,
    status: str | None = None,
) -> list[dict]:
    """
    查请假记录。

    - 不传 student_id：查全部，给后台列表用；
    - 传 student_id：先确认学生存在，再查该学生；
    - 返回时批量补学生姓名和审批人姓名。
    """
    if student_id is not None:
        identity_api.ensure_student(student_id)

    rows = repository.list_leaves(student_id, status)
    return _attach_names(rows)


def approve_leave(leave_id: int, approver_id: int, approved: bool) -> dict:
    """
    审批请假。

    只有“待审批”的记录可以审批；已通过 / 已驳回再次审批返回 409。
    """
    identity_api.ensure_employee(approver_id)

    leave = get_leave(leave_id)
    if leave["status"] != "待审批":
        raise ConflictError(
            f"请假记录 {leave_id} 当前状态为 {leave['status']}，不能重复审批"
        )

    new_status = "已通过" if approved else "已驳回"
    repository.update_leave_status(leave_id, approver_id, new_status)
    return get_leave(leave_id)


# ============================================================
# 售后反馈
# ============================================================
def create_feedback(payload: FeedbackCreate) -> dict:
    """提交售后反馈，初始状态“待处理”。"""
    identity_api.ensure_student(payload.student_id)
    ticket_id = repository.create_feedback(
        student_id=payload.student_id,
        content=payload.content,
        detail=payload.detail,
    )
    return repository.get_feedback(ticket_id)


def list_feedback(
    student_id: int | None = None,
    status: str | None = None,
) -> list[dict]:
    """
    查售后工单。

    - 不传 student_id：查全部，给后台列表用；
    - 传 student_id：先确认学生存在，再查该学生；
    - 返回时批量补学生姓名。
    """
    if student_id is not None:
        identity_api.ensure_student(student_id)

    rows = repository.list_feedback(student_id, status)
    return _attach_names(rows)


def resolve_feedback(ticket_id: int, solution: str) -> dict:
    """解决工单：状态置为已解决，并标记已通知学生。"""
    ticket = repository.get_feedback(ticket_id)
    if not ticket:
        raise NotFoundError(f"售后工单 {ticket_id} 不存在")
    if ticket["status"] == "已解决":
        raise ConflictError(f"售后工单 {ticket_id} 已经解决")

    repository.resolve_feedback(ticket_id, solution)
    return repository.get_feedback(ticket_id)


def delete_feedback(ticket_id: int, student_id: int | None) -> dict:
    """
    撤销（删除）售后工单。

    - student_id 有值：只能删本人的工单，且未解决才能撤销（已解决的走正常归档）；
    - student_id 为 None：员工/管理员，可删任意工单。
    删除前先返回被删记录，供接口回显。
    """
    ticket = repository.get_feedback(ticket_id)
    if not ticket:
        raise NotFoundError(f"售后工单 {ticket_id} 不存在")

    # 学生只能撤销自己的工单（越权直接拒绝）
    if student_id is not None and ticket["student_id"] != student_id:
        raise NotFoundError(f"售后工单 {ticket_id} 不存在")

    # 已解决的工单不允许学生撤销（避免误删归档记录）；员工可强制删除
    if student_id is not None and ticket["status"] == "已解决":
        raise ConflictError(f"售后工单 {ticket_id} 已解决，无法撤销")

    repository.delete_feedback(ticket_id)
    return ticket


# ============================================================
# 成绩
# ============================================================
# ============================================================
# 已报课程（客户签约后开通）
# ============================================================
def list_my_courses(student_id: int) -> dict:
    """
    学生课程页数据。

    1. 先确认学生存在；
    2. 有签约线索（crm_lead.status='已签约' 且姓名匹配）或已开通课程 → signed=True；
    3. 返回已报课程列表；为空时前端展示「可报项目」。
    """
    users = identity_api.get_users_by_ids([student_id])
    if not users:
        raise NotFoundError(f"学生 {student_id} 不存在")
    student = users[0]

    items = repository.list_enrollments(student_id)

    # 签约判断只认「是否已开通课程」：签约动作会同时写入 enrollment，
    # 这样学生模块不需要反向依赖员工模块（保持依赖单向）。
    return {
        "student_id": student_id,
        "signed": bool(items),
        "lead_status": None,
        "lead_name": None,
        "items": items,
    }


def enroll_course(payload: EnrollmentCreate) -> dict:
    """
    给学生开通已签约课程。

    业务契约：客户签约 → 确定所报课程 → 写入学生个人系统。
    同一个项目不重复开通。
    """
    identity_api.ensure_student(payload.student_id)

    project = catalog_api.get_project(payload.project_id)
    if not project:
        raise NotFoundError(f"课程项目 {payload.project_id} 不存在")

    existed = [
        item for item in repository.list_enrollments(payload.student_id)
        if item["project_id"] == payload.project_id
    ]
    if existed:
        raise ConflictError(f"学生 {payload.student_id} 已经开通「{project['project_name']}」")

    enrollment_id = repository.create_enrollment(
        student_id=payload.student_id,
        project_id=payload.project_id,
        project_name=project["project_name"],
        source_lead_id=payload.source_lead_id,
        signed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    return repository.get_enrollment(enrollment_id)


def record_score(payload: ScoreCreate) -> dict:
    """录入成绩；分数由 Pydantic 限制在 0~100。"""
    identity_api.ensure_student(payload.student_id)
    score_id = repository.create_score(
        student_id=payload.student_id,
        course_name=payload.course_name,
        score=payload.score,
        semester=payload.semester,
    )
    return repository.get_score(score_id)


def list_scores(
    student_id: int | None = None,
    course_name: str | None = None,
) -> list[dict]:
    """
    查成绩。

    - 不传 student_id：查全部，给后台列表用；
    - 传 student_id：先确认学生存在，再查该学生；
    - 返回时批量补学生姓名。
    """
    if student_id is not None:
        identity_api.ensure_student(student_id)

    rows = repository.list_scores(student_id, course_name)
    return _attach_names(rows)


def update_score(score_id: int, payload: ScoreUpdate) -> dict:
    """
    修改成绩：先确认记录存在，再只更新传了的字段。

    - 一个字段都不传 → 400，避免“改了个寂寞”；
    - score 的 0~100 范围由 Pydantic 保证（和录入一致）。
    """
    score = repository.get_score(score_id)
    if not score:
        raise NotFoundError(f"成绩记录 {score_id} 不存在")

    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise BadRequestError("至少要提供一个要修改的字段")

    repository.update_score(
        score_id,
        course_name=changes.get("course_name"),
        score=changes.get("score"),
        semester=changes.get("semester"),
    )
    return repository.get_score(score_id)


def delete_score(score_id: int) -> dict:
    """删除成绩：先确认存在，返回被删记录便于前端提示。"""
    score = repository.get_score(score_id)
    if not score:
        raise NotFoundError(f"成绩记录 {score_id} 不存在")
    repository.delete_score(score_id)
    return score
