"""
员工业务模块的 Service（业务层）。

职责：
- 客户线索：录入、查询、状态流转；
- 员工日报：提交、查询。

跨模块调用只走 app.identity.api。
"""

from __future__ import annotations

from datetime import date

from app.employee.schemas import (
    LeadCreate,
    LeadSignRequest,
    LeadStatusUpdate,
    LeadUpdate,
    ReportCreate,
    ReportUpdate,
)
from app.identity import api as identity_api
from app.shared.errors import BadRequestError, ConflictError, NotFoundError

from . import repository

# 客户状态白名单，和 schemas.LeadStatus 保持一致
VALID_LEAD_STATUS = {"新增意向", "跟进中", "已签约", "已流失"}


def create_lead(payload: LeadCreate) -> dict:
    """录入意向客户：先确认负责员工存在。"""
    identity_api.ensure_employee(payload.owner_employee_id)

    lead_id = repository.create_lead(
        customer_name=payload.customer_name,
        contact_info=payload.contact_info,
        background_info=payload.background_info,
        follow_up_history=payload.follow_up_history or "[]",
        owner_employee_id=payload.owner_employee_id,
    )
    return repository.get_lead(lead_id)


def list_leads(
    status: str | None = None,
    owner_employee_id: int | None = None,
    keyword: str | None = None,
) -> list[dict]:
    """查客户线索。"""
    if status and status not in VALID_LEAD_STATUS:
        raise BadRequestError(f"非法客户状态：{status}")
    return repository.list_leads(status, owner_employee_id, keyword)


def get_leads_by_ids(lead_ids: list[int]) -> list[dict]:
    """批量查客户线索，供其他模块补姓名 / 联系方式。"""
    return repository.get_leads_by_ids(lead_ids)


def find_signed_lead(name: str) -> dict | None:
    """按姓名找已签约线索；没有返回 None。"""
    if not name:
        return None
    return repository.find_signed_lead_by_name(name)


def update_lead_status(lead_id: int, payload: LeadStatusUpdate) -> dict:
    """
    更新客户状态。

    只允许四种状态；记录不存在返回 404。
    """
    lead = repository.get_lead(lead_id)
    if not lead:
        raise NotFoundError(f"客户线索 {lead_id} 不存在")

    if payload.status not in VALID_LEAD_STATUS:
        raise BadRequestError(f"非法客户状态：{payload.status}")

    repository.update_lead_status(lead_id, payload.status)
    return repository.get_lead(lead_id)


def update_lead(lead_id: int, payload: LeadUpdate) -> dict:
    """编辑客户资料：先确认存在，再只更新传了的字段。"""
    lead = repository.get_lead(lead_id)
    if not lead:
        raise NotFoundError(f"客户线索 {lead_id} 不存在")

    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise BadRequestError("至少要提供一个要修改的字段")

    repository.update_lead(
        lead_id,
        customer_name=changes.get("customer_name"),
        contact_info=changes.get("contact_info"),
        background_info=changes.get("background_info"),
        follow_up_history=changes.get("follow_up_history"),
    )
    return repository.get_lead(lead_id)


def delete_lead(lead_id: int) -> dict:
    """
    删除客户线索（带安全闸）。

    已签约的线索不能删：签约时会创建学生账号并写入选课（source_lead_id=lead_id），
    删掉会让这些关联数据悬空。要终止合作请改为「已流失」状态。
    """
    lead = repository.get_lead(lead_id)
    if not lead:
        raise NotFoundError(f"客户线索 {lead_id} 不存在")
    if lead["status"] == "已签约":
        raise ConflictError(
            f"客户线索 {lead_id} 已签约，不能删除；如需终止合作请改为「已流失」"
        )
    repository.delete_lead(lead_id)
    return lead


def create_report(payload: ReportCreate) -> dict:
    """提交日报；不传日期时默认当天。"""
    identity_api.ensure_employee(payload.employee_id)

    report_date = (payload.report_date or date.today()).isoformat()
    report_id = repository.create_report(
        employee_id=payload.employee_id,
        report_date=report_date,
        content=payload.content,
    )
    return repository.get_report(report_id)


def list_reports(
    employee_id: int | None = None,
    report_date: str | None = None,
) -> list[dict]:
    """查日报。"""
    return repository.list_reports(employee_id, report_date)


def update_report(report_id: int, payload: ReportUpdate) -> dict:
    """修改日报：先确认存在，再只更新传了的字段。"""
    report = repository.get_report(report_id)
    if not report:
        raise NotFoundError(f"日报 {report_id} 不存在")

    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise BadRequestError("至少要提供一个要修改的字段")

    report_date = changes.get("report_date")
    repository.update_report(
        report_id,
        content=changes.get("content"),
        report_date=report_date.isoformat() if report_date else None,
    )
    return repository.get_report(report_id)


def delete_report(report_id: int) -> dict:
    """删除日报：先确认存在，返回被删记录。"""
    report = repository.get_report(report_id)
    if not report:
        raise NotFoundError(f"日报 {report_id} 不存在")
    repository.delete_report(report_id)
    return report


def sign_lead(lead_id: int, payload: LeadSignRequest) -> dict:
    """
    签约并开通课程（**签约是建账号的前置条件**）。

    流程：
    1. 校验线索与课程存在；
    2. 按姓名找学生：有就复用，没有才创建账号（未签约的人不会提前进系统）；
    3. 线索状态改为「已签约」；
    4. 把报读课程写入该学生的个人系统（重复开通不报错，提示已开通）。

    注意：这里用函数内 import 引入 student 模块，
    因为 student 模块的 service 也依赖 employee 的 api，顶层互相 import 会成环。
    """
    lead = repository.get_lead(lead_id)
    if not lead:
        raise NotFoundError(f"客户线索 {lead_id} 不存在")

    real_name = (payload.real_name or lead.get("customer_name") or "").strip()
    if not real_name:
        raise BadRequestError("客户姓名为空，无法创建学生账号")

    existed = [u for u in identity_api.list_students() if u.get("real_name") == real_name]
    account_created = False

    if existed:
        student = existed[0]
    else:
        student = identity_api.create_student(
            real_name=real_name,
            username=payload.username,
            contact_info=lead.get("contact_info"),
        )
        account_created = True

    repository.update_lead_status(lead_id, "已签约")

    # 延迟导入，避免与 student 模块循环依赖
    from app.shared.errors import ConflictError
    from app.student import api as student_api
    from app.student.schemas import EnrollmentCreate

    enrollment = None
    enrollment_id: int | None = None
    already = False
    try:
        enrollment = student_api.enroll_course(
            EnrollmentCreate(
                student_id=int(student["id"]),
                project_id=payload.project_id,
                source_lead_id=lead_id,
            )
        )
        enrollment_id = int(enrollment["id"])
    except ConflictError:
        already = True

    # 课程名由学生模块返回（它负责校验课程存在），员工模块不直接依赖课程模块
    project_name = (enrollment or {}).get("project_name")

    if already:
        message = f"{real_name} 已签约；账号 {student['username']} 此前已开通「{project_name}」"
    elif account_created:
        message = f"{real_name} 已签约，已创建学生账号 {student['username']}，并开通「{project_name}」"
    else:
        message = f"{real_name} 已签约，已为账号 {student['username']} 开通「{project_name}」"

    return {
        "lead_id": lead_id,
        "lead_status": "已签约",
        "student_id": int(student["id"]),
        "username": student["username"],
        "real_name": student["real_name"],
        "account_created": account_created,
        "enrollment_id": enrollment_id,
        "project_name": project_name,
        "message": message,
    }
