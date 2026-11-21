"""
心理关怀模块的 Service（业务层）。

核心规则（来自需求文档）：
- 情绪分 >= 70：高危，写预警表 + 通知班主任；
- 40 <= 情绪分 < 70：关注；
- 情绪分 < 40：正常。

情绪分来源：
1. 优先用上游（Dify / 大模型）传入的 emotion_score；
2. 没传时用关键词兜底，保证脱离大模型也能独立测试。
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from app.identity import api as identity_api
from app.psych.schemas import (
    AlertUpdate,
    ConversationCreate,
    EmotionAssessRequest,
)
from app.shared.errors import NotFoundError

from . import repository

# 高危关键词：命中直接 90 分。
# 分三类，便于后续维护：
#   1) 自伤 / 自杀倾向
#   2) 对他人或群体的暴力倾向（“我要去砍人”这类必须命中）
#   3) 极端绝望表达
HIGH_RISK_WORDS = [
    # 自伤 / 自杀
    "自杀", "想死", "去死", "死了算了", "不想活", "活不下去", "活着没意思", "活着没意义",
    "结束生命", "了结自己", "轻生", "跳楼", "跳河", "割腕", "割手", "上吊", "喝药",
    "安眠药", "自残", "自伤", "伤害自己", "不想醒来",
    # 暴力 / 伤人
    "砍人", "砍死", "砍他", "砍你", "去砍", "杀人", "杀他", "杀你", "杀了", "想杀", "要杀",
    "捅死", "捅人", "捅他", "弄死", "打死", "掐死", "毒死", "炸死", "开枪", "带刀",
    "拿刀", "动刀", "血洗", "报复社会", "同归于尽", "拉垫背",
    # 极端绝望
    "崩溃到极点", "撑不下去", "没有出路", "生不如死", "彻底绝望",
]

# 负面关键词：命中 55 分
NEGATIVE_WORDS = [
    "焦虑", "抑郁", "失眠", "压力", "难过", "崩溃", "孤独", "害怕", "无助",
    "烦躁", "委屈", "想哭", "厌学", "学不进去", "被孤立", "被欺负", "挂科",
    "失恋", "吵架", "睡不着", "心慌", "自卑",
]

# 积极关键词：命中 15 分
POSITIVE_WORDS = ["开心", "高兴", "谢谢", "很好", "喜欢", "期待", "轻松", "有进步", "适应了"]

# 归一化时要剔除的字符：空白 + 中英文标点 + 符号
_STRIP_PATTERN = re.compile(r"[\s\u3000，。！？、,.!?;；:：\"'“”‘’（）()\[\]【】…~\-—_/\\|*#@&^%$+=<>《》]+")


def _normalize(text: str) -> str:
    """
    去掉空白与标点后再匹配。

    否则「我 要 去 砍 人」「砍、人」这类写法会绕过关键词表。
    """
    return _STRIP_PATTERN.sub("", text or "")


def match_emotion(text: str) -> tuple[str, int, str] | None:
    """
    命中明确情绪关键词时，返回 (标签, 分值, 风险)；没命中返回 None。

    这个函数用来做“强信号校验”：
    如果文本里明确写了“开心 / 抑郁 / 不想活”，
    就不应该被上游误传的分数覆盖。
    """
    content = _normalize(text)

    if any(word in content for word in HIGH_RISK_WORDS):
        return "高危", 90, "高"

    if any(word in content for word in NEGATIVE_WORDS):
        return "负面", 55, "中"

    if any(word in content for word in POSITIVE_WORDS):
        return "积极", 15, "低"

    return None


def evaluate_emotion(text: str) -> tuple[str, int, str]:
    """
    关键词兜底评估。

    命中关键词按关键词给分；完全没命中时按“平稳 20 分”处理。
    """
    matched = match_emotion(text)
    if matched:
        return matched
    return "平稳", 20, "低"


def risk_from_score(score: int) -> str:
    """按分值换算风险等级。"""
    if score >= 70:
        return "高"
    if score >= 40:
        return "中"
    return "低"


def tag_from_score(score: int) -> str:
    """没有标签时，按分值给一个默认标签。"""
    if score >= 70:
        return "高危"
    if score >= 40:
        return "负面"
    if score >= 20:
        return "平稳"
    return "积极"


def assess_emotion(payload: EmotionAssessRequest) -> dict:
    """
    评估学生情绪，并完成三件事：
    1. 更新心理画像（保留最近 50 条历史）；
    2. 高危时写入预警表；
    3. 写一条对话记录。
    """
    identity_api.ensure_student(payload.student_id)

    # 1. 文本里有明确关键词：以关键词为准。
    #    这样即使上游误传了 emotion_score=90，“开心”也不会被判成高危。
    matched = match_emotion(payload.text)

    if matched:
        tag, score, risk = matched

    # 2. 没有明确关键词，但上游给了分数：使用上游分数。
    elif payload.emotion_score is not None:
        score = int(payload.emotion_score)
        tag = payload.emotion_tag or tag_from_score(score)
        risk = risk_from_score(score)

    # 3. 只给了标签没给分数：按标签换算一个默认分。
    elif payload.emotion_tag:
        tag = payload.emotion_tag
        score = 90 if tag == "高危" else 55 if tag == "负面" else 20
        risk = risk_from_score(score)

    # 4. 什么都没给：按平稳处理。
    else:
        tag, score, risk = "平稳", 20, "低"

    # 读取旧历史，追加本次，只保留最近 50 条
    existing = repository.get_profile(payload.student_id)
    history: list[dict] = []
    if existing:
        try:
            history = json.loads(existing.get("emotion_history") or "[]")
        except (TypeError, ValueError):
            history = []

    history.append(
        {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tag": tag,
            "score": score,
        }
    )
    history = history[-50:]

    repository.upsert_profile(
        student_id=payload.student_id,
        emotion_tag=tag,
        emotion_score=score,
        emotion_history=json.dumps(history, ensure_ascii=False),
    )

    # 高危：写预警
    alerted = False
    alert_id: int | None = None
    message = f"当前情绪：{tag}，分值 {score}，风险等级 {risk}。"

    if score >= 70:
        alert_id = repository.create_alert(
            student_id=payload.student_id,
            trigger_reason=payload.text[:200],
            risk_level=risk,
        )
        alerted = True
        message = "已触发高危预警并通知班主任，请尽快关注该学生。"

    # 对话记录：给心理画像提供情绪原料
    repository.create_conversation(
        user_id=payload.student_id,
        agent_type="student",
        user_input=payload.text,
        ai_output=message,
        emotion_tag=tag,
    )

    return {
        "student_id": payload.student_id,
        "emotion_tag": tag,
        "emotion_score": score,
        "risk_level": risk,
        "alerted": alerted,
        "alert_id": alert_id,
        "message": message,
    }


def _attach_names(rows: list[dict]) -> list[dict]:
    """
    给预警记录补“学生姓名”和“跟进老师姓名”。

    通过 identity.api 批量取，不直接查 sys_user 表，也避免 N+1。
    """
    related_ids: set[int] = set()
    for row in rows:
        if row.get("student_id") is not None:
            related_ids.add(row["student_id"])
        if row.get("teacher_id") is not None:
            related_ids.add(row["teacher_id"])

    users = identity_api.get_users_by_ids(sorted(related_ids))
    name_map = {user["id"]: user["real_name"] for user in users}

    for row in rows:
        row["student_name"] = name_map.get(row.get("student_id"))
        row["teacher_name"] = name_map.get(row.get("teacher_id"))

    return rows


def get_profile(student_id: int) -> dict:
    """查心理画像；历史情绪从 JSON 字符串还原成列表。"""
    profile = repository.get_profile(student_id)
    if not profile:
        raise NotFoundError(f"学生 {student_id} 还没有心理画像")

    try:
        history = json.loads(profile.get("emotion_history") or "[]")
    except (TypeError, ValueError):
        history = []

    return {**profile, "emotion_history": history}


def list_alerts(status: str | None = None) -> list[dict]:
    """查预警列表，返回时带学生姓名。"""
    rows = repository.list_alerts(status)
    return _attach_names(rows)


def update_alert(alert_id: int, payload: AlertUpdate) -> dict:
    """更新预警处理状态；如果传了 teacher_id，先确认是员工。"""
    alert = repository.get_alert(alert_id)
    if not alert:
        raise NotFoundError(f"预警 {alert_id} 不存在")

    if payload.teacher_id is not None:
        identity_api.ensure_employee(payload.teacher_id)

    repository.update_alert(alert_id, payload.status, payload.teacher_id)
    updated = repository.get_alert(alert_id)
    return _attach_names([updated])[0]


def log_conversation(payload: ConversationCreate) -> dict:
    """写一条对话记录。"""
    identity_api.get_user(payload.user_id)
    conversation_id = repository.create_conversation(
        user_id=payload.user_id,
        agent_type=payload.agent_type,
        user_input=payload.user_input,
        ai_output=payload.ai_output,
        emotion_tag=payload.emotion_tag,
    )
    return repository.get_conversation(conversation_id)


def list_conversations(user_id: int, limit: int = 50) -> list[dict]:
    """
    查某个用户最近的对话记录。

    repository 早已有这个函数，之前没暴露出来——数据只写不查。
    这里做薄封装，数据范围由 router 的 scope_student_id 控制：
    学生只能传自己（越权请求被纠正成 uid），员工/管理员可查任意用户。
    """
    return repository.list_conversations(user_id, limit)
