"""
心理关怀模块的 Repository（数据访问层）。

涉及三张表：
- student_psych_profile  心理画像
- student_psych_alert    心理预警
- conversation_log       对话记录
"""

from __future__ import annotations

from app.shared.db import get_connection, row_to_dict, rows_to_dicts


# ============================================================
# 心理画像
# ============================================================
def get_profile(student_id: int) -> dict | None:
    """按学生 id 查心理画像。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM student_psych_profile WHERE student_id = ?",
            (student_id,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def upsert_profile(
    student_id: int,
    emotion_tag: str,
    emotion_score: int,
    emotion_history: str,
) -> None:
    """
    写入或更新心理画像。

    一个学生只有一条画像，用 ON CONFLICT(student_id) 做 upsert：
    - 不存在：插入；
    - 已存在：更新情绪标签、分值、交互时间、历史。
    """
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO student_psych_profile
                (student_id, latest_emotion_tag, emotion_score,
                 last_interaction_time, emotion_history)
            VALUES (?, ?, ?, datetime('now'), ?)
            ON CONFLICT(student_id) DO UPDATE SET
                latest_emotion_tag = excluded.latest_emotion_tag,
                emotion_score = excluded.emotion_score,
                last_interaction_time = excluded.last_interaction_time,
                emotion_history = excluded.emotion_history,
                update_time = CURRENT_TIMESTAMP
            """,
            (student_id, emotion_tag, emotion_score, emotion_history),
        )
        conn.commit()
    finally:
        conn.close()


# ============================================================
# 心理预警
# ============================================================
def create_alert(student_id: int, trigger_reason: str, risk_level: str) -> int:
    """插入一条预警，返回 id。"""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO student_psych_alert
                (student_id, trigger_reason, risk_level, status)
            VALUES (?, ?, ?, '未处理')
            """,
            (student_id, trigger_reason, risk_level),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_alert(alert_id: int) -> dict | None:
    """按 id 查一条预警。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM student_psych_alert WHERE id = ?",
            (alert_id,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def list_alerts(status: str | None = None) -> list[dict]:
    """查预警列表，可按状态过滤。"""
    sql = "SELECT * FROM student_psych_alert WHERE 1 = 1"
    params: list[object] = []

    if status:
        sql += " AND status = ?"
        params.append(status)

    sql += " ORDER BY id DESC"

    conn = get_connection()
    try:
        return rows_to_dicts(conn.execute(sql, params).fetchall())
    finally:
        conn.close()


def update_alert(alert_id: int, status: str, teacher_id: int | None) -> None:
    """更新预警状态；teacher_id 有值才更新跟进老师。"""
    conn = get_connection()
    try:
        if teacher_id is None:
            conn.execute(
                "UPDATE student_psych_alert SET status = ? WHERE id = ?",
                (status, alert_id),
            )
        else:
            conn.execute(
                "UPDATE student_psych_alert SET status = ?, teacher_id = ? WHERE id = ?",
                (status, teacher_id, alert_id),
            )
        conn.commit()
    finally:
        conn.close()


# ============================================================
# 对话记录
# ============================================================
def create_conversation(
    user_id: int,
    agent_type: str,
    user_input: str,
    ai_output: str | None,
    emotion_tag: str | None,
) -> int:
    """写一条对话记录，返回 id。"""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO conversation_log
                (user_id, agent_type, user_input, ai_output, emotion_tag)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, agent_type, user_input, ai_output, emotion_tag),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_conversation(conversation_id: int) -> dict | None:
    """按 id 查一条对话记录。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM conversation_log WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def list_conversations(user_id: int, limit: int = 50) -> list[dict]:
    """查某个用户的最近对话。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM conversation_log
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return rows_to_dicts(rows)
    finally:
        conn.close()
