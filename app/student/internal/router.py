"""
学生事务模块的 Router（Controller 层）。

只负责 HTTP 入参 / 出参，不写业务规则。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.shared.deps import (
    force_self_id,
    get_current_user,
    require_staff,
    scope_student_id,
)

from app.student.schemas import (
    EnrollmentCreate,
    EnrollmentOut,
    FeedbackCreate,
    FeedbackOut,
    FeedbackResolve,
    LeaveApprove,
    LeaveCreate,
    LeaveOut,
    MyCoursesOut,
    ScoreCreate,
    ScoreOut,
    ScoreUpdate,
)

from .service import (
    approve_leave,
    create_feedback,
    create_leave,
    delete_feedback,
    enroll_course,
    list_feedback,
    list_leaves,
    list_my_courses,
    list_scores,
    record_score,
    resolve_feedback,
    delete_score,
    update_score,
)

router = APIRouter()


# ============================================================
# 请假
# ============================================================
@router.post(
    "/leaves",
    response_model=LeaveOut,
    status_code=status.HTTP_201_CREATED,
    summary="提交请假申请",
)
def create_leave_api(payload: LeaveCreate, user: dict = Depends(get_current_user)) -> dict:
    """POST /api/student/leaves（学生只能给自己提交）"""
    payload = payload.model_copy(update={"student_id": force_self_id(user, payload.student_id)})
    return create_leave(payload)


@router.get(
    "/leaves",
    response_model=list[LeaveOut],
    summary="查学生的请假记录",
)
def list_leaves_api(
    student_id: int | None = Query(
        None,
        description="学生编号；不传则查全部（后台列表用）",
    ),
    leave_status: str | None = Query(
        None,
        alias="status",
        description="待审批/已通过/已驳回",
    ),
    user: dict = Depends(get_current_user),
) -> list[dict]:
    """GET /api/student/leaves（学生只能看自己）"""
    return list_leaves(scope_student_id(user, student_id), leave_status)


@router.post(
    "/leaves/{leave_id}/approve",
    response_model=LeaveOut,
    summary="审批请假",
)
def approve_leave_api(
    leave_id: int,
    payload: LeaveApprove,
    user: dict = Depends(require_staff),
) -> dict:
    """POST /api/student/leaves/{leave_id}/approve（员工审批，审批人取 token）"""
    return approve_leave(leave_id, int(user["uid"]) or payload.approver_id, payload.approved)


# ============================================================
# 售后反馈
# ============================================================
@router.post(
    "/feedback",
    response_model=FeedbackOut,
    status_code=status.HTTP_201_CREATED,
    summary="提交售后反馈",
)
def create_feedback_api(payload: FeedbackCreate, user: dict = Depends(get_current_user)) -> dict:
    """POST /api/student/feedback（学生只能给自己提交）"""
    payload = payload.model_copy(update={"student_id": force_self_id(user, payload.student_id)})
    return create_feedback(payload)


@router.get(
    "/feedback",
    response_model=list[FeedbackOut],
    summary="查学生的售后工单",
)
def list_feedback_api(
    student_id: int | None = Query(
        None,
        description="学生编号；不传则查全部（后台列表用）",
    ),
    feedback_status: str | None = Query(
        None,
        alias="status",
        description="待处理/处理中/已解决",
    ),
    user: dict = Depends(get_current_user),
) -> list[dict]:
    """GET /api/student/feedback（学生只能看自己）"""
    return list_feedback(scope_student_id(user, student_id), feedback_status)


@router.post(
    "/feedback/{ticket_id}/resolve",
    response_model=FeedbackOut,
    summary="解决售后工单并通知",
)
def resolve_feedback_api(
    ticket_id: int,
    payload: FeedbackResolve,
    user: dict = Depends(require_staff),
) -> dict:
    """POST /api/student/feedback/{ticket_id}/resolve（员工处理）"""
    return resolve_feedback(ticket_id, payload.solution)


@router.delete(
    "/feedback/{ticket_id}",
    response_model=FeedbackOut,
    summary="撤销售后工单",
)
def delete_feedback_api(
    ticket_id: int,
    user: dict = Depends(get_current_user),
) -> dict:
    """DELETE /api/student/feedback/{ticket_id}（学生只能撤自己的；员工可撤任意）"""
    scoped = scope_student_id(user, None)
    return delete_feedback(ticket_id, int(scoped) if scoped is not None else None)


# ============================================================
# 成绩
# ============================================================
@router.get(
    "/scores",
    response_model=list[ScoreOut],
    summary="查成绩（可按学生 / 课程过滤）",
)
def list_all_scores_api(
    student_id: int | None = Query(
        None,
        description="学生编号；不传则查全部（后台列表用）",
    ),
    course_name: str | None = Query(None, description="课程名，支持模糊匹配"),
    user: dict = Depends(get_current_user),
) -> list[dict]:
    """GET /api/student/scores（学生只能看自己）"""
    return list_scores(scope_student_id(user, student_id), course_name)


@router.post(
    "/scores",
    response_model=ScoreOut,
    status_code=status.HTTP_201_CREATED,
    summary="录入成绩",
)
def record_score_api(payload: ScoreCreate, user: dict = Depends(require_staff)) -> dict:
    """POST /api/student/scores（员工/老师录入）"""
    return record_score(payload)


@router.patch(
    "/scores/{score_id}",
    response_model=ScoreOut,
    summary="修改成绩（只改传了的字段）",
)
def update_score_api(
    score_id: int,
    payload: ScoreUpdate,
    user: dict = Depends(require_staff),
) -> dict:
    """PATCH /api/student/scores/{score_id}（员工/老师，score_id 从路径取）"""
    return update_score(score_id, payload)


@router.delete(
    "/scores/{score_id}",
    response_model=ScoreOut,
    summary="删除成绩",
)
def delete_score_api(
    score_id: int,
    user: dict = Depends(require_staff),
) -> dict:
    """DELETE /api/student/scores/{score_id}（员工/老师）"""
    return delete_score(score_id)


# ============================================================
# 已报课程（客户签约后开通）
# ============================================================
@router.get(
    "/enrollments",
    response_model=MyCoursesOut,
    summary="我的课程：先判断是否签约，再返回已报课程",
)
def my_courses_api(
    student_id: int = Query(..., description="学生编号"),
    user: dict = Depends(get_current_user),
) -> dict:
    """GET /api/student/enrollments（学生只能看自己）"""
    return list_my_courses(int(scope_student_id(user, student_id)))


@router.post(
    "/enrollments",
    response_model=EnrollmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="给学生开通已签约课程",
)
def enroll_course_api(payload: EnrollmentCreate, user: dict = Depends(require_staff)) -> dict:
    """POST /api/student/enrollments（员工签约后开通）"""
    return enroll_course(payload)
