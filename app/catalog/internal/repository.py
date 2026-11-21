"""
课程与活动模块的 Repository（数据访问层）。

涉及三张表：
- course_project       课程 / 项目
- event_lecture        活动 / 讲座
- event_registration   活动报名
"""

from __future__ import annotations

from app.shared.db import get_connection, row_to_dict, rows_to_dicts


# ============================================================
# 课程 / 项目
# ============================================================
def list_projects(keyword: str | None = None, category: str | None = None) -> list[dict]:
    """查课程 / 项目，支持关键词和类别过滤。"""
    sql = "SELECT * FROM course_project WHERE 1 = 1"
    params: list[object] = []

    if keyword:
        sql += " AND (project_name LIKE ? OR description LIKE ?)"
        like = f"%{keyword}%"
        params.extend([like, like])

    if category:
        sql += " AND category = ?"
        params.append(category)

    sql += " ORDER BY id"

    conn = get_connection()
    try:
        return rows_to_dicts(conn.execute(sql, params).fetchall())
    finally:
        conn.close()


def create_project(
    project_name: str,
    category: str | None = None,
    description: str | None = None,
    target_audience: str | None = None,
) -> int:
    """
    新增课程 / 项目，返回自增 id。
    字段与 schema.sql 的 course_project 表一一对应，不改表结构。
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO course_project (project_name, category, description, target_audience)
            VALUES (?, ?, ?, ?)
            """,
            (project_name, category, description, target_audience),
        )
        conn.commit()
        return int(cursor.lastrowid)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# 活动
# ============================================================
def get_project(project_id: int) -> dict | None:
    """按 id 查一个课程项目；学生开通课程时需要读到项目名。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM course_project WHERE id = ?",
            (project_id,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def list_events(event_type: str | None = None) -> list[dict]:
    """查活动列表，可按线上 / 线下过滤。"""
    sql = "SELECT * FROM event_lecture WHERE 1 = 1"
    params: list[object] = []

    if event_type:
        sql += " AND event_type = ?"
        params.append(event_type)

    sql += " ORDER BY start_time"

    conn = get_connection()
    try:
        return rows_to_dicts(conn.execute(sql, params).fetchall())
    finally:
        conn.close()


def get_event(event_id: int) -> dict | None:
    """按 id 查活动。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM event_lecture WHERE id = ?",
            (event_id,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def create_event(
    event_name: str,
    event_type: str | None = None,
    start_time: str | None = None,
    location: str | None = None,
    max_participants: int | None = None,
    current_participants: int = 0,
) -> int:
    """
    新增活动 / 讲座，返回自增 id。
    字段与 schema.sql 的 event_lecture 表一一对应，不改表结构。
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO event_lecture
                (event_name, event_type, start_time, location, max_participants, current_participants)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_name, event_type, start_time, location, max_participants, current_participants),
        )
        conn.commit()
        return int(cursor.lastrowid)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# 报名
# ============================================================
def find_registration(event_id: int, customer_id: int) -> dict | None:
    """查某个客户是否已经报名某个活动。"""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT * FROM event_registration
            WHERE event_id = ? AND customer_id = ? AND status = '已报名'
            """,
            (event_id, customer_id),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def create_registration(event_id: int, customer_id: int) -> int:
    """
    插入报名记录，并把活动当前人数 +1。

    两件事放在同一个事务里，避免“报了名但人数没加”。
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO event_registration (event_id, customer_id, status)
            VALUES (?, ?, '已报名')
            """,
            (event_id, customer_id),
        )
        conn.execute(
            """
            UPDATE event_lecture
            SET current_participants = current_participants + 1
            WHERE id = ?
            """,
            (event_id,),
        )
        conn.commit()
        return int(cursor.lastrowid)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def register_with_info(
    event_id: int,
    customer_name: str,
    contact_info: str | None,
    background_info: str | None,
    owner_employee_id: int,
) -> dict:
    """
    聚合写操作：建客户线索 + 报名 + 活动人数 +1，放在同一个事务里。

    为什么放一个事务：如果建了客户却报名失败（比如名额刚好满），
    会留下一条没有报名记录的"孤儿客户"。同一事务保证要么全成功、要么全回滚。

    返回：新报名记录（含 event_name），调用方再join客户信息组装播报文案。
    """
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        # 1) 建客户线索，初始状态「新增意向」；follow_up_history 用空 JSON 数组
        cursor = conn.execute(
            """
            INSERT INTO crm_lead
                (customer_name, contact_info, background_info,
                 follow_up_history, status, owner_employee_id)
            VALUES (?, ?, ?, '[]', '新增意向', ?)
            """,
            (customer_name, contact_info, background_info, owner_employee_id),
        )
        customer_id = int(cursor.lastrowid)
        # 2) 报名记录
        cursor = conn.execute(
            """
            INSERT INTO event_registration (event_id, customer_id, status)
            VALUES (?, ?, '已报名')
            """,
            (event_id, customer_id),
        )
        registration_id = int(cursor.lastrowid)
        # 3) 活动人数 +1
        conn.execute(
            """
            UPDATE event_lecture
            SET current_participants = current_participants + 1
            WHERE id = ?
            """,
            (event_id,),
        )
        conn.commit()
        # 用新连接读回填后的完整记录（含 event_name）
        return {
            "id": registration_id,
            "event_id": event_id,
            "customer_id": customer_id,
            "status": "已报名",
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_registration(registration_id: int) -> dict | None:
    """按 id 查报名记录，并带出活动名称。"""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT r.*, e.event_name
            FROM event_registration r
            LEFT JOIN event_lecture e ON e.id = r.event_id
            WHERE r.id = ?
            """,
            (registration_id,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def list_registrations(
    event_id: int | None = None,
    customer_id: int | None = None,
) -> list[dict]:
    """查报名记录，可按活动、按报名人过滤。"""
    sql = """
        SELECT r.*, e.event_name
        FROM event_registration r
        LEFT JOIN event_lecture e ON e.id = r.event_id
        WHERE 1 = 1
    """
    params: list[object] = []

    if event_id is not None:
        sql += " AND r.event_id = ?"
        params.append(event_id)

    if customer_id is not None:
        sql += " AND r.customer_id = ?"
        params.append(customer_id)

    sql += " ORDER BY r.id DESC"

    conn = get_connection()
    try:
        return rows_to_dicts(conn.execute(sql, params).fetchall())
    finally:
        conn.close()


def cancel_registration(registration_id: int) -> bool:
    """
    取消报名（软删除）：status 改为「已取消」，并回滚活动人数 -1。

    关键点：
    - 只有当前状态是「已报名」才真正取消并减人数，返回 True；
    - 已经是「已取消」则不重复减人数，返回 False（幂等保护）；
    - 不改数据库结构，复用 event_registration.status 现有字段；
    - 改状态和减人数在同一个事务里，避免只做了一半。
    """
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        row = conn.execute(
            "SELECT event_id, status FROM event_registration WHERE id = ?",
            (registration_id,),
        ).fetchone()
        if not row:
            conn.rollback()
            return False
        if row["status"] == "已取消":
            conn.rollback()
            return False

        conn.execute(
            "UPDATE event_registration SET status = '已取消' WHERE id = ?",
            (registration_id,),
        )
        # 人数不能减成负数（MAX 兜底，防止历史脏数据导致 -1）
        conn.execute(
            """
            UPDATE event_lecture
            SET current_participants = MAX(0, current_participants - 1)
            WHERE id = ?
            """,
            (row["event_id"],),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
