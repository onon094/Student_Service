"""课程与活动模块的公开数据结构（DTO）。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProjectOut(BaseModel):
    """课程 / 项目。"""

    id: int
    project_name: str
    category: str | None = None
    description: str | None = None
    target_audience: str | None = None


class EventOut(BaseModel):
    """活动 / 讲座。"""

    id: int
    event_name: str
    event_type: str | None = None
    start_time: str
    location: str | None = None
    max_participants: int | None = None
    current_participants: int = 0


class EventCreate(BaseModel):
    """新增活动 / 讲座入参（仅前端管理后台的真人调用，不对 Dify 暴露）。"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_name": "新加坡留学开放日",
                "event_type": "线下",
                "start_time": "2026-12-01 14:00:00",
                "location": "广州天河校区",
                "max_participants": 50,
            }
        }
    )

    # min_length=1 拦截纯空名称；start_time 必填，避免前台显示空时间
    event_name: str = Field(min_length=1, description="活动名称，必填")
    event_type: str | None = Field(default=None, description="线上 / 线下")
    start_time: str = Field(min_length=1, description="开始时间，格式 YYYY-MM-DD HH:MM:SS")
    location: str | None = Field(default=None, description="地点或线上链接")
    max_participants: int | None = Field(default=None, ge=1, description="最大报名人数")
    # 新建活动从 0 人开始，字段保留仅为兼容表结构，前端不需要传
    current_participants: int = Field(default=0, ge=0, description="当前报名人数，默认 0")


class ProjectCreate(BaseModel):
    """新增课程 / 项目入参（仅前端管理后台的真人调用，不对 Dify 暴露）。"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_name": "德国双元制项目",
                "category": "德国项目",
                "description": "带薪双元制，企业对接",
                "target_audience": "高中毕业生",
            }
        }
    )

    project_name: str = Field(min_length=1, description="项目 / 课程名称，必填")
    category: str | None = Field(default=None, description="类别：语言培训/背景提升/国际本科 等")
    description: str | None = Field(default=None, description="项目介绍")
    target_audience: str | None = Field(default=None, description="适合人群 / 学历要求")


class RegisterRequest(BaseModel):
    """活动报名入参。"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "customer_id": 1,
            }
        }
    )

    customer_id: int = Field(
        gt=0,
        description="客户线索 id（crm_lead.id），不是学生 id",
    )


class RegisterWithInfoRequest(BaseModel):
    """
    带真实客户信息的活动报名入参（智能体/客服对话用）。

    与 RegisterRequest 的区别：那个只收已有的 customer_id，
    这个直接收姓名+电话，后端先建客户线索再报名，一步完成。
    这样游客在对话里说「我叫X，电话Y，要报名」就能真实登记。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "customer_name": "李明",
                "contact_info": "13900002222",
                "background_info": "高三在读，想了解新加坡本科",
            }
        }
    )

    customer_name: str = Field(min_length=1, max_length=50, description="客户姓名，必填")
    contact_info: str | None = Field(default=None, description="联系方式（电话/邮箱），可选")
    background_info: str | None = Field(default=None, description="客户背景/意向，可选")


class RegistrationOut(BaseModel):
    """
    报名记录。

    除了外键 id，还返回客户姓名和联系方式，
    这样后台列表直接可读，不用前端再查一次。
    """

    id: int
    event_id: int
    customer_id: int
    status: str
    create_time: str | None = None
    event_name: str | None = None
    customer_name: str | None = None
    contact_info: str | None = None


class RegisterWithInfoOut(BaseModel):
    """建档+报名聚合接口出参：明确带回真实姓名和活动名，供智能体如实播报。"""

    success: bool
    registration_id: int | None = None
    customer_id: int | None = None
    customer_name: str | None = None
    event_id: int
    event_name: str | None = None
    status: str | None = None
    message: str | None = None
