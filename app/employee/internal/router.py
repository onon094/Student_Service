"""
员工业务模块的 Router（Controller 层）。

只负责 HTTP 入参 / 出参。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.shared.deps import get_current_user, require_staff

from app.employee.schemas import (
    LeadCreate,
    LeadOut,
    LeadSignRequest,
    LeadSignResult,
    LeadStatusUpdate,
    LeadUpdate,
    ReportCreate,
    ReportOut,
    ReportUpdate,
)

from .service import (
    create_lead,
    create_report,
    delete_lead,
    delete_report,
    list_leads,
    list_reports,
    sign_lead,
    update_lead,
    update_lead_status,
    update_report,
)

router = APIRouter()


# ============================================================
# 客户线索
# ============================================================
@router.post(
    "/leads",
    response_model=LeadOut,
    status_code=status.HTTP_201_CREATED,
    summary="录入意向客户",
)
def create_lead_api(payload: LeadCreate) -> dict:
    """POST /api/employee/leads（官网表单可匿名提交）"""
    return create_lead(payload)


@router.get(
    "/leads",
    response_model=list[LeadOut],
    summary="查客户线索",
)
def list_leads_api(
    lead_status: str | None = Query(None, alias="status", description="新增意向/跟进中/已签约/已流失"),
    owner_employee_id: int | None = Query(None, description="负责员工编号"),
    keyword: str | None = Query(None, description="姓名或背景关键词"),
    user: dict = Depends(require_staff),
) -> list[dict]:
    """GET /api/employee/leads?status=跟进中&keyword=许"""
    return list_leads(lead_status, owner_employee_id, keyword)


@router.patch(
    "/leads/{lead_id}/status",
    response_model=LeadOut,
    summary="更新客户状态",
)
def update_lead_status_api(
    lead_id: int,
    payload: LeadStatusUpdate,
    user: dict = Depends(require_staff),
) -> dict:
    """PATCH /api/employee/leads/1/status"""
    return update_lead_status(lead_id, payload)


@router.patch(
    "/leads/{lead_id}",
    response_model=LeadOut,
    summary="编辑客户资料",
)
def update_lead_api(
    lead_id: int,
    payload: LeadUpdate,
    user: dict = Depends(require_staff),
) -> dict:
    """PATCH /api/employee/leads/1（只改资料，状态和负责人走各自接口）"""
    return update_lead(lead_id, payload)


@router.delete(
    "/leads/{lead_id}",
    response_model=LeadOut,
    summary="删除客户线索（已签约禁止删除）",
)
def delete_lead_api(
    lead_id: int,
    user: dict = Depends(require_staff),
) -> dict:
    """DELETE /api/employee/leads/1（已签约返回 409，请改为已流失）"""
    return delete_lead(lead_id)


@router.post(
    "/leads/{lead_id}/sign",
    response_model=LeadSignResult,
    status_code=status.HTTP_201_CREATED,
    summary="签约并开通课程（签约时才创建学生账号）",
)
def sign_lead_api(
    lead_id: int,
    payload: LeadSignRequest,
    user: dict = Depends(require_staff),
) -> dict:
    """POST /api/employee/leads/3/sign"""
    return sign_lead(lead_id, payload)


# ============================================================
# 员工日报
# ============================================================
@router.post(
    "/reports",
    response_model=ReportOut,
    status_code=status.HTTP_201_CREATED,
    summary="提交员工日报",
)
def create_report_api(payload: ReportCreate, user: dict = Depends(require_staff)) -> dict:
    """POST /api/employee/reports（日报归属当前登录员工）"""
    payload = payload.model_copy(update={"employee_id": int(user["uid"]) or payload.employee_id})
    return create_report(payload)


@router.get(
    "/reports",
    response_model=list[ReportOut],
    summary="查员工日报",
)
def list_reports_api(
    employee_id: int | None = Query(None, description="员工编号"),
    report_date: str | None = Query(None, description="日期，格式 YYYY-MM-DD"),
    user: dict = Depends(require_staff),
) -> list[dict]:
    """GET /api/employee/reports?employee_id=7&report_date=2026-11-17"""
    return list_reports(employee_id, report_date)


@router.patch(
    "/reports/{report_id}",
    response_model=ReportOut,
    summary="修改日报",
)
def update_report_api(
    report_id: int,
    payload: ReportUpdate,
    user: dict = Depends(require_staff),
) -> dict:
    """PATCH /api/employee/reports/1（内容和日期只改传了的）"""
    return update_report(report_id, payload)


@router.delete(
    "/reports/{report_id}",
    response_model=ReportOut,
    summary="删除日报",
)
def delete_report_api(
    report_id: int,
    user: dict = Depends(require_staff),
) -> dict:
    """DELETE /api/employee/reports/1"""
    return delete_report(report_id)
