"""员工业务模块的公开数据结构（DTO）。"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 客户状态只允许这四种，和需求文档保持一致
LeadStatus = Literal["新增意向", "跟进中", "已签约", "已流失"]


class LeadCreate(BaseModel):
    """录入意向客户。"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "customer_name": "许同学",
                "contact_info": "13800001111",
                "background_info": "高三在读，想去新加坡读本科",
                "follow_up_history": "[]",
                "owner_employee_id": 7,
            }
        }
    )

    customer_name: str = Field(min_length=1, max_length=50)
    contact_info: str | None = None
    background_info: str | None = None
    follow_up_history: str = "[]"
    owner_employee_id: int


class LeadUpdate(BaseModel):
    """
    编辑客户资料（只改这几列，都是可选，只传要改的）。

    刻意不含 status 和 owner_employee_id：
    - 状态流转走 PATCH /leads/{id}/status，有白名单校验；
    - 负责人变更是另一类权限操作，不混在资料编辑里。
    """

    model_config = ConfigDict(
        json_schema_extra={"example": {"customer_name": "许同学", "contact_info": "13900009999"}}
    )

    customer_name: str | None = Field(default=None, min_length=1, max_length=50)
    contact_info: str | None = None
    background_info: str | None = None
    follow_up_history: str | None = None


class LeadStatusUpdate(BaseModel):
    """更新客户状态。"""

    status: LeadStatus


class LeadOut(BaseModel):
    """客户线索。"""

    id: int
    customer_name: str
    contact_info: str | None = None
    background_info: str | None = None
    follow_up_history: str | None = None
    status: str
    owner_employee_id: int
    create_time: str | None = None
    update_time: str | None = None


class ReportCreate(BaseModel):
    """提交员工日报；不传日期时默认当天。"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "employee_id": 7,
                "content": "今天跟进 3 个客户，签约 1 个",
            }
        }
    )

    employee_id: int
    report_date: date | None = None
    content: str = Field(min_length=1, max_length=2000)


class ReportOut(BaseModel):
    """员工日报。"""

    id: int
    employee_id: int
    report_date: str
    content: str
    create_time: str | None = None


class ReportUpdate(BaseModel):
    """修改日报：内容和日期都可选，只传要改的。"""

    model_config = ConfigDict(
        json_schema_extra={"example": {"content": "补充：今天又跟进了 2 个客户"}}
    )

    content: str | None = Field(default=None, min_length=1, max_length=2000)
    report_date: date | None = None


class LeadSignRequest(BaseModel):
    """
    签约并开通课程。

    业务契约：**签约时才创建学生账号**。
    - project_id：客户报的具体课程，必填；
    - username：不传就按 lead_<id> 自动生成，重名自动加序号；
    - real_name：不传就用客户姓名。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"project_id": 2, "username": "student_li", "real_name": "李四"}
        }
    )

    project_id: int = Field(ge=1)
    username: str | None = Field(default=None, max_length=50)
    real_name: str | None = Field(default=None, max_length=50)


class LeadSignResult(BaseModel):
    """签约结果：账号是否新建、开了哪门课。"""

    lead_id: int
    lead_status: str
    student_id: int
    username: str
    real_name: str
    account_created: bool
    enrollment_id: int | None = None
    project_name: str | None = None
    message: str
