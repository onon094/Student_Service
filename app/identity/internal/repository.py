"""
身份模块的 Repository（数据访问层）。

职责：只写 SQL，不做业务判断。
"""

from __future__ import annotations

from app.shared.db import get_connection, row_to_dict, rows_to_dicts


def get_user(user_id: int) -> dict | None:
    """按 id 查一个用户。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM sys_user WHERE id = ?",
            (user_id,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def get_users_by_ids(user_ids: list[int]) -> list[dict]:
    """
    批量查用户，给其他模块补姓名用。

    用 IN (?, ?, ...) 一次查完，避免 N+1。
    """
    if not user_ids:
        return []

    placeholders = ",".join("?" for _ in user_ids)
    sql = f"SELECT * FROM sys_user WHERE id IN ({placeholders})"

    conn = get_connection()
    try:
        return rows_to_dicts(conn.execute(sql, user_ids).fetchall())
    finally:
        conn.close()


def get_user_by_username(username: str) -> dict | None:
    """按用户名查用户，创建账号前用来判重。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM sys_user WHERE username = ?",
            (username,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def create_user(
    username: str,
    password_hash: str,
    real_name: str,
    user_type: str,
    employee_role: str | None = None,
    department: str | None = None,
    contact_info: str | None = None,
) -> int:
    """
    新增一个用户（学生或员工），返回新 id。

    只写字段，不做业务校验；重名、角色合法性由 service 层决定。
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO sys_user
                (username, password_hash, real_name, user_type, employee_role, department, contact_info, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, '正常')
            """,
            (username, password_hash, real_name, user_type, employee_role, department, contact_info),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def list_users(
    user_type: str | None = None,
    department: str | None = None,
) -> list[dict]:
    """
    按类型 / 部门查用户列表。

    - user_type: STUDENT / EMPLOYEE
    - department: 部门名称
    """
    sql = "SELECT * FROM sys_user WHERE 1 = 1"
    params: list[object] = []

    if user_type:
        sql += " AND user_type = ?"
        params.append(user_type)

    if department:
        sql += " AND department = ?"
        params.append(department)

    sql += " ORDER BY id"

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        return rows_to_dicts(rows)
    finally:
        conn.close()
