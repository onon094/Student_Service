"""学生事务模块的公开数据结构（DTO）。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LeaveCreate(BaseModel):
    """
    提交请假申请。

    正确用法：只填 student_id + reason，起止时间留空，后端会从 reason 里解析。
    service_type 只允许“请假 / 考务查询”，不要把请假事由填到这里。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "student_id": 1,
                "reason": "明天请假一天，家里有事",
            }
        }
    )

    student_id: int
    service_type: Literal["请假", "考务查询"] = "请假"
    start_time: datetime | None = None
    end_time: datetime | None = None
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def check_time_range(self) -> "LeaveCreate":
        """
        时间校验：防止把 start_time 和 end_time 填成同一个时间。

        - 只填一个：报错；
        - 开始时间 >= 结束时间：报错。
        """
        if (self.start_time is None) != (self.end_time is None):
            raise ValueError("start_time 和 end_time 要么都填，要么都不填")

        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValueError("开始时间必须早于结束时间，不能相同")

        return self


class LeaveApprove(BaseModel):
    """审批请假：approved=True 通过，False 驳回。"""

    approver_id: int
    approved: bool


class LeaveOut(BaseModel):
    """请假记录；除了 student_id，还返回学生姓名，方便后台直接展示。"""

    id: int
    student_id: int
    student_name: str | None = None
    service_type: str
    start_time: str | None = None
    end_time: str | None = None
    reason: str | None = None
    status: str
    approver_id: int | None = None
    approver_name: str | None = None
    create_time: str | None = None


class FeedbackCreate(BaseModel):
    """提交售后反馈 / 投诉。"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "student_id": 1,
                "content": "宿舍空调坏了",
                "detail": "已经报修两天，还没人处理",
            }
        }
    )

    student_id: int
    content: str = Field(min_length=1, max_length=200)
    detail: str | None = None


class FeedbackResolve(BaseModel):
    """解决工单时填写的方案。"""

    solution: str = Field(min_length=1, max_length=500)


class FeedbackOut(BaseModel):
    """售后工单；带 student_name，后台列表直接可读。"""

    id: int
    student_id: int
    student_name: str | None = None
    content: str
    detail: str | None = None
    status: str
    solution: str | None = None
    is_notified: int = 0
    create_time: str | None = None


class ScoreCreate(BaseModel):
    """录入成绩：分数限制在 0~100。"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "student_id": 1,
                "course_name": "Python",
                "score": 92,
                "semester": "2026-秋季",
            }
        }
    )

    student_id: int
    course_name: str = Field(min_length=1, max_length=50)
    score: float = Field(ge=0, le=100)
    semester: str | None = None


class ScoreOut(BaseModel):
    """成绩记录；带 student_name，后台列表直接可读。"""

    id: int
    student_id: int
    student_name: str | None = None
    course_name: str
    score: float
    semester: str | None = None
    create_time: str | None = None


class ScoreUpdate(BaseModel):
    """
    修改成绩：三个字段都可选，只传要改的那几个。

    - 分数仍限制 0~100（和录入一致）；
    - 至少传一个字段，否则无意义（service 层拦截）；
    - student_id 不允许改：成绩归属不能转移，要改就删了重录。
    """

    model_config = ConfigDict(
        json_schema_extra={"example": {"score": 95, "semester": "2027-春季"}}
    )

    course_name: str | None = Field(default=None, min_length=1, max_length=50)
    score: float | None = Field(default=None, ge=0, le=100)
    semester: str | None = None


# ============================================================
# 已报课程（客户签约后开通）
# ============================================================
class EnrollmentCreate(BaseModel):
    """给学生开通一门已签约课程。"""

    student_id: int
    project_id: int
    source_lead_id: int | None = None


class EnrollmentOut(BaseModel):
    """学生已报课程。"""

    id: int
    student_id: int
    project_id: int
    project_name: str
    status: str
    signed_at: str
    create_time: str | None = None


class MyCoursesOut(BaseModel):
    """
    学生课程页的完整返回。

    signed：是否已签约（有签约线索或已开通课程）
    items：已报课程；为空时前端展示可报项目
    """

    student_id: int
    signed: bool
    lead_status: str | None = None
    lead_name: str | None = None
    items: list[EnrollmentOut] = []
