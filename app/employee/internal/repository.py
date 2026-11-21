"""
员工业务模块的 Repository（数据访问层）。

涉及两张表：
- crm_lead               客户线索
- employee_daily_report  员工日报
"""

from __future__ import annotations

from app.shared.db import get_connection, row_to_dict, rows_to_dicts


# ============================================================
# 客户线索
# ============================================================
def create_lead(
    customer_name: str,
    contact_info: str | None,
    background_info: str | None,
    follow_up_history: str,
    owner_employee_id: int,
) -> int:
    """插入一条客户线索，初始状态“新增意向”。"""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO crm_lead
                (customer_name, contact_info, background_info,
                 follow_up_history, status, owner_employee_id)
            VALUES (?, ?, ?, ?, '新增意向', ?)
            """,
            (customer_name, contact_info, background_info, follow_up_history, owner_employee_id),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_lead(lead_id: int) -> dict | None:
    """按 id 查一条客户线索。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM crm_lead WHERE id = ?",
            (lead_id,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def list_leads(
    status: str | None = None,
    owner_employee_id: int | None = None,
    keyword: str | None = None,
) -> list[dict]:
    """
    查客户线索，支持：
    - 按状态过滤；
    - 按负责员工过滤；
    - 关键词模糊匹配姓名 / 背景。
    """
    sql = "SELECT * FROM crm_lead WHERE 1 = 1"
    params: list[object] = []

    if status:
        sql += " AND status = ?"
        params.append(status)

    if owner_employee_id is not None:
        sql += " AND owner_employee_id = ?"
        params.append(owner_employee_id)

    if keyword:
        sql += " AND (customer_name LIKE ? OR background_info LIKE ?)"
        like = f"%{keyword}%"
        params.extend([like, like])

    sql += " ORDER BY id DESC"

    conn = get_connection()
    try:
        return rows_to_dicts(conn.execute(sql, params).fetchall())
    finally:
        conn.close()


def get_leads_by_ids(lead_ids: list[int]) -> list[dict]:
    """
    批量查客户线索。

    给其他模块（例如 catalog 查报名记录）补客户姓名用，
    避免一条一条查造成 N+1。
    """
    if not lead_ids:
        return []

    placeholders = ",".join("?" for _ in lead_ids)
    sql = f"SELECT * FROM crm_lead WHERE id IN ({placeholders})"

    conn = get_connection()
    try:
        return rows_to_dicts(conn.execute(sql, lead_ids).fetchall())
    finally:
        conn.close()


def find_signed_lead_by_name(name: str) -> dict | None:
    """按客户姓名查「已签约」的线索；学生课程页据此判断是否已签约。"""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT * FROM crm_lead
            WHERE customer_name = ? AND status = '已签约'
            ORDER BY id DESC LIMIT 1
            """,
            (name,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def update_lead_status(lead_id: int, status: str) -> None:
    """更新客户状态。"""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE crm_lead
            SET status = ?, update_time = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, lead_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_lead(
    lead_id: int,
    customer_name: str | None = None,
    contact_info: str | None = None,
    background_info: str | None = None,
    follow_up_history: str | None = None,
) -> None:
    """编辑客户资料：只更新传入的字段（None 表示不改这一列）。"""
    sets: list[str] = []
    params: list[object] = []

    if customer_name is not None:
        sets.append("customer_name = ?")
        params.append(customer_name)
    if contact_info is not None:
        sets.append("contact_info = ?")
        params.append(contact_info)
    if background_info is not None:
        sets.append("background_info = ?")
        params.append(background_info)
    if follow_up_history is not None:
        sets.append("follow_up_history = ?")
        params.append(follow_up_history)

    if not sets:
        return

    sets.append("update_time = CURRENT_TIMESTAMP")
    params.append(lead_id)
    conn = get_connection()
    try:
        conn.execute(
            f"UPDATE crm_lead SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        conn.commit()
    finally:
        conn.close()


def delete_lead(lead_id: int) -> None:
    """删除一条客户线索（调用方 service 已拦住已签约的记录）。"""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM crm_lead WHERE id = ?", (lead_id,))
        conn.commit()
    finally:
        conn.close()


# ============================================================
# 员工日报
# ============================================================
def create_report(employee_id: int, report_date: str, content: str) -> int:
    """插入一条日报。"""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO employee_daily_report (employee_id, report_date, content)
            VALUES (?, ?, ?)
            """,
            (employee_id, report_date, content),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_report(report_id: int) -> dict | None:
    """按 id 查一条日报。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM employee_daily_report WHERE id = ?",
            (report_id,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def list_reports(
    employee_id: int | None = None,
    report_date: str | None = None,
) -> list[dict]:
    """查日报，可按员工 / 日期过滤。"""
    sql = "SELECT * FROM employee_daily_report WHERE 1 = 1"
    params: list[object] = []

    if employee_id is not None:
        sql += " AND employee_id = ?"
        params.append(employee_id)

    if report_date:
        sql += " AND report_date = ?"
        params.append(report_date)

    sql += " ORDER BY id DESC"

    conn = get_connection()
    try:
        return rows_to_dicts(conn.execute(sql, params).fetchall())
    finally:
        conn.close()


def update_report(report_id: int, content: str | None, report_date: str | None) -> None:
    """修改日报：只更新传入的字段。"""
    sets: list[str] = []
    params: list[object] = []
    if content is not None:
        sets.append("content = ?")
        params.append(content)
    if report_date is not None:
        sets.append("report_date = ?")
        params.append(report_date)
    if not sets:
        return

    params.append(report_id)
    conn = get_connection()
    try:
        conn.execute(
            f"UPDATE employee_daily_report SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        conn.commit()
    finally:
        conn.close()


def delete_report(report_id: int) -> None:
    """删除一条日报。employee_daily_report 无外键引用，物理删除安全。"""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM employee_daily_report WHERE id = ?", (report_id,))
        conn.commit()
    finally:
        conn.close()
