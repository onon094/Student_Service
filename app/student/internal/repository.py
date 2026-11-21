"""
学生事务模块的 Repository（数据访问层）。

只写 SQL，不做业务判断。
涉及三张表：
- student_admin_service   请假 / 考务
- student_feedback_ticket 售后工单
- student_score           成绩
"""

from __future__ import annotations

from app.shared.db import get_connection, row_to_dict, rows_to_dicts


# ============================================================
# 请假
# ============================================================
def create_leave(
    student_id: int,
    service_type: str,
    start_time: str,
    end_time: str,
    reason: str,
) -> int:
    """插入一条请假申请，返回新记录 id。"""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO student_admin_service
                (student_id, service_type, start_time, end_time, reason, status)
            VALUES (?, ?, ?, ?, ?, '待审批')
            """,
            (student_id, service_type, start_time, end_time, reason),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_leave(leave_id: int) -> dict | None:
    """按 id 查一条请假记录。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM student_admin_service WHERE id = ?",
            (leave_id,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def list_leaves(
    student_id: int | None = None,
    status: str | None = None,
) -> list[dict]:
    """
    查请假记录。

    - student_id 不传：查全部（后台列表用）；
    - student_id 传了：只看这个学生；
    - status 可选：按审批状态过滤。
    """
    sql = "SELECT * FROM student_admin_service WHERE 1 = 1"
    params: list[object] = []

    if student_id is not None:
        sql += " AND student_id = ?"
        params.append(student_id)

    if status:
        sql += " AND status = ?"
        params.append(status)

    sql += " ORDER BY id DESC"

    conn = get_connection()
    try:
        return rows_to_dicts(conn.execute(sql, params).fetchall())
    finally:
        conn.close()


def update_leave_status(leave_id: int, approver_id: int, status: str) -> None:
    """更新请假审批结果。"""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE student_admin_service
            SET status = ?, approver_id = ?, update_time = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, approver_id, leave_id),
        )
        conn.commit()
    finally:
        conn.close()


# ============================================================
# 售后反馈
# ============================================================
def create_feedback(student_id: int, content: str, detail: str | None) -> int:
    """插入一条售后工单，返回新记录 id。"""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO student_feedback_ticket
                (student_id, content, detail, status, is_notified)
            VALUES (?, ?, ?, '待处理', 0)
            """,
            (student_id, content, detail),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_feedback(ticket_id: int) -> dict | None:
    """按 id 查一条售后工单。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM student_feedback_ticket WHERE id = ?",
            (ticket_id,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def delete_feedback(ticket_id: int) -> bool:
    """按 id 物理删除一条售后工单；返回是否删到了。"""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM student_feedback_ticket WHERE id = ?",
            (ticket_id,),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def list_feedback(
    student_id: int | None = None,
    status: str | None = None,
) -> list[dict]:
    """
    查售后工单。

    - student_id 不传：查全部（后台列表用）；
    - student_id 传了：只看这个学生；
    - status 可选：按处理状态过滤。
    """
    sql = "SELECT * FROM student_feedback_ticket WHERE 1 = 1"
    params: list[object] = []

    if student_id is not None:
        sql += " AND student_id = ?"
        params.append(student_id)

    if status:
        sql += " AND status = ?"
        params.append(status)

    sql += " ORDER BY id DESC"

    conn = get_connection()
    try:
        return rows_to_dicts(conn.execute(sql, params).fetchall())
    finally:
        conn.close()


def resolve_feedback(ticket_id: int, solution: str) -> None:
    """把工单标记为已解决，并记录已通知学生。"""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE student_feedback_ticket
            SET status = '已解决',
                solution = ?,
                is_notified = 1,
                update_time = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (solution, ticket_id),
        )
        conn.commit()
    finally:
        conn.close()


# ============================================================
# 成绩
# ============================================================
def create_enrollment(
    student_id: int,
    project_id: int,
    project_name: str,
    source_lead_id: int | None,
    signed_at: str,
) -> int:
    """写入一条学生已报课程，返回 id。"""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO student_enrollment
                (student_id, project_id, project_name, source_lead_id, status, signed_at)
            VALUES (?, ?, ?, ?, '在读', ?)
            """,
            (student_id, project_id, project_name, source_lead_id, signed_at),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_enrollment(enrollment_id: int) -> dict | None:
    """按 id 查一条已报课程。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM student_enrollment WHERE id = ?",
            (enrollment_id,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def list_enrollments(student_id: int) -> list[dict]:
    """查某个学生的全部已报课程。"""
    conn = get_connection()
    try:
        return rows_to_dicts(
            conn.execute(
                "SELECT * FROM student_enrollment WHERE student_id = ? ORDER BY id DESC",
                (student_id,),
            ).fetchall()
        )
    finally:
        conn.close()


def create_score(
    student_id: int,
    course_name: str,
    score: float,
    semester: str | None,
) -> int:
    """插入一条成绩记录。"""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO student_score (student_id, course_name, score, semester)
            VALUES (?, ?, ?, ?)
            """,
            (student_id, course_name, score, semester),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_score(score_id: int) -> dict | None:
    """按 id 查一条成绩。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM student_score WHERE id = ?",
            (score_id,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def list_scores(
    student_id: int | None = None,
    course_name: str | None = None,
) -> list[dict]:
    """
    查成绩。

    - student_id 不传：查全部（后台列表用）；
    - student_id 传了：只看这个学生；
    - course_name 可选：按课程名模糊匹配。
    """
    sql = "SELECT * FROM student_score WHERE 1 = 1"
    params: list[object] = []

    if student_id is not None:
        sql += " AND student_id = ?"
        params.append(student_id)

    if course_name:
        sql += " AND course_name LIKE ?"
        params.append(f"%{course_name}%")

    sql += " ORDER BY id DESC"

    conn = get_connection()
    try:
        return rows_to_dicts(conn.execute(sql, params).fetchall())
    finally:
        conn.close()


def update_score(
    score_id: int,
    course_name: str | None = None,
    score: float | None = None,
    semester: str | None = None,
) -> None:
    """
    修改成绩：只更新传入的字段（None 表示不改这一列）。

    用拼 SQL 的方式支持“只改部分字段”，列名是代码里的固定白名单，
    不存在 SQL 注入风险； semester 允许传空字符串来清空。
    """
    sets: list[str] = []
    params: list[object] = []

    if course_name is not None:
        sets.append("course_name = ?")
        params.append(course_name)
    if score is not None:
        sets.append("score = ?")
        params.append(score)
    if semester is not None:
        sets.append("semester = ?")
        params.append(semester)

    if not sets:
        return  # 没有要改的字段，service 层已拦截，这里兜底

    params.append(score_id)
    conn = get_connection()
    try:
        conn.execute(
            f"UPDATE student_score SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        conn.commit()
    finally:
        conn.close()


def delete_score(score_id: int) -> None:
    """删除一条成绩。student_score 无外键引用，物理删除不影响其他表。"""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM student_score WHERE id = ?", (score_id,))
        conn.commit()
    finally:
        conn.close()
