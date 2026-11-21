"""
SQLite 基础设施
---------------
职责：
1. 提供数据库连接（Row 工厂 + 外键约束）。
2. 提供事务上下文管理器。
3. 启动时执行 schema.sql 建表。
4. 空库时写入演示种子数据。

注意：
- 所有业务 SQL 写在各自模块的 repository.py，不写在这里。
- 这里只做“连接 / 建表 / 种子”这类公共能力。
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from app.shared.config import DB_PATH, DEFAULT_DEMO_PASSWORD, SCHEMA_PATH
from app.shared.security import hash_password, needs_rehash


def get_connection() -> sqlite3.Connection:
    """
    创建并返回一个 SQLite 连接。

    - row_factory = sqlite3.Row：查询结果可以用 row["字段名"] 访问。
    - PRAGMA foreign_keys = ON：SQLite 默认不强制外键，每条连接都要开。
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """
    事务上下文：

        with transaction() as conn:
            conn.execute(...)

    正常结束提交，异常回滚，最后一定关闭连接。
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


EXTRA_SCHEMA = """
-- 学生已报课程：客户签约后由顾问开通，写入学生个人系统。
-- 单独放这里，不修改老师给的 schema.sql。
CREATE TABLE IF NOT EXISTS student_enrollment (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   INTEGER NOT NULL,
    project_id   INTEGER NOT NULL,
    project_name TEXT    NOT NULL,
    source_lead_id INTEGER,
    status       TEXT    NOT NULL DEFAULT '在读',
    signed_at    TEXT    NOT NULL,
    create_time  TEXT    DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db() -> None:
    """执行 schema.sql 建 12 张表，再补建学生课程表（都可重复执行）。"""
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection()
    try:
        conn.executescript(schema)
        conn.executescript(EXTRA_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    """把单行 sqlite3.Row 转成普通 dict；没有数据返回 None。"""
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    """把多行 sqlite3.Row 转成 dict 列表，方便直接返回 JSON。"""
    return [{key: row[key] for key in row.keys()} for row in rows]


def seed_if_empty() -> None:
    """
    空库时写入演示数据。

    判断条件：sys_user 表是否有数据。
    只要 sys_user 不为空，就认为已经初始化过，不重复插入。
    """
    conn = get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) AS c FROM sys_user").fetchone()["c"]
        if count > 0:
            return

        # ---------- 1. 用户：学生 + 员工 ----------
        demo_hash = hash_password(DEFAULT_DEMO_PASSWORD)
        users = [
            (1, "student_zhang", demo_hash, "张三", "STUDENT", None, "新加坡本科班", "13800000001", "正常"),
            (2, "student_li", demo_hash, "李四", "STUDENT", None, "新加坡本科班", "13800000002", "正常"),
            (3, "student_wang", demo_hash, "王五", "STUDENT", None, "德国双元制班", "13800000003", "正常"),
            (4, "student_zhao", demo_hash, "赵六", "STUDENT", None, "新加坡本科班", "13800000004", "正常"),
            (5, "student_sun", demo_hash, "孙七", "STUDENT", None, "新加坡本科班", "13800000005", "正常"),
            (6, "teacher_chen", demo_hash, "陈老师", "EMPLOYEE", "班主任", "教学部", "13900000001", "正常"),
            (7, "sales_lin", demo_hash, "林顾问", "EMPLOYEE", "普通员工", "销售部", "13900000002", "正常"),
            (8, "leader_zhou", demo_hash, "周领导", "EMPLOYEE", "领导", "管理部", "13900000003", "正常"),
            (9, "admin_sys", demo_hash, "系统管理员", "EMPLOYEE", "管理员", "管理部", "13900000004", "正常"),
        ]
        conn.executemany(
            """
            INSERT INTO sys_user
                (id, username, password_hash, real_name, user_type,
                 employee_role, department, contact_info, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            users,
        )

        # ---------- 2. 课程 / 项目 ----------
        projects = [
            (
                "2+2 新加坡定向培养本科班",
                "国际本科",
                "国内 2 年 + 新加坡 2 年，获世界排名 200-500 大学本科文凭",
                "应往届初中毕业生",
            ),
            (
                "0.5/1+2 新加坡定向培养本科班",
                "国际本科",
                "国内 0.5/1 年预科 + 新加坡 2 年本科，入学门槛低",
                "高二在读、应往届高中 / 中职中技毕业生",
            ),
            (
                "2+2+1 新加坡本硕连读",
                "本硕连读",
                "2+2 本科毕业后可直升 1 年制硕士，可申请 TOP200 名校",
                "应往届初中毕业生",
            ),
            (
                "0.5/1+2+1 新加坡本硕连读",
                "本硕连读",
                "0.5/1+2 本科毕业后可直升 1 年制硕士",
                "高中 / 中职毕业生",
            ),
            (
                "6+6 酒店运营大专就业班",
                "就业班",
                "6 个月理论 + 6 个月带薪实习，一年获大专文凭，推荐就业",
                "职高 / 中专 / 中职 / 技校，满 17 岁",
            ),
            (
                "9+6 航空运营大专就业班",
                "就业班",
                "9 个月理论 + 6 个月带薪实习，一年获大专文凭，推荐就业",
                "职高 / 中专 / 中职 / 技校，满 17 岁",
            ),
            (
                "一年制专升本",
                "学历提升",
                "国内专科升本科，约 1-1.5 年，学历回国可认证",
                "国内专科毕业生",
            ),
            (
                "一年制本升硕",
                "学历提升",
                "国内本科升硕士，约 1 年，可申请海外名校",
                "国内本科毕业生",
            ),
            (
                "德国双元制",
                "德国项目",
                "国内德语培训 + 德国企业实训，可就业、升学或申请永居",
                "18-35 岁，高中及以上学历，德语 B1，动手能力强",
            ),
        ]
        conn.executemany(
            """
            INSERT INTO course_project
                (project_name, category, description, target_audience)
            VALUES (?, ?, ?, ?)
            """,
            projects,
        )

        # ---------- 3. 活动 / 讲座 ----------
        events = [
            ("新加坡留学分享会", "线上", "2026-12-05 19:30:00", "腾讯会议（报名后发链接）", 100, 0),
            ("德国双元制招生官见面会", "线下", "2026-12-12 14:00:00", "广州天河校区", 50, 0),
        ]
        conn.executemany(
            """
            INSERT INTO event_lecture
                (event_name, event_type, start_time, location, max_participants, current_participants)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            events,
        )

        # ---------- 4. 意向客户 ----------
        leads = [
            ("许同学", "13800001111", "高三在读，想去新加坡读本科", "[]", "新增意向", 7),
            ("李同学", "13800002222", "大专毕业，想专升本", "[]", "跟进中", 7),
        ]
        conn.executemany(
            """
            INSERT INTO crm_lead
                (customer_name, contact_info, background_info, follow_up_history, status, owner_employee_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            leads,
        )

        # ---------- 5. 成绩 ----------
        scores = [
            (1, "Python", 92, "2026-秋季"),
            (1, "英语", 85, "2026-秋季"),
            (2, "Python", 78, "2026-秋季"),
            (3, "德语", 88, "2026-秋季"),
        ]
        conn.executemany(
            """
            INSERT INTO student_score (student_id, course_name, score, semester)
            VALUES (?, ?, ?, ?)
            """,
            scores,
        )

        # ---------- 6. 心理画像示例 ----------
        conn.execute(
            """
            INSERT INTO student_psych_profile
                (student_id, latest_emotion_tag, emotion_score, last_interaction_time, emotion_history)
            VALUES (?, ?, ?, datetime('now'), ?)
            """,
            (1, "平稳", 20, json.dumps([], ensure_ascii=False)),
        )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def migrate_passwords() -> int:
    """
    把占位符 / 旧格式的密码哈希迁移成 PBKDF2。

    历史数据里 password_hash 全是字面量 'hash'，直接登录会全部失败；
    启动时统一替换成 DEFAULT_DEMO_PASSWORD 的哈希。返回迁移条数。
    """
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, password_hash FROM sys_user").fetchall()
        changed = 0
        for row in rows:
            if needs_rehash(row["password_hash"] or ""):
                conn.execute(
                    "UPDATE sys_user SET password_hash = ? WHERE id = ?",
                    (hash_password(DEFAULT_DEMO_PASSWORD), row["id"]),
                )
                changed += 1
        if changed:
            conn.commit()
        return changed
    finally:
        conn.close()
