"""
NL2SQL 模块的 Repository（只读数据访问层）。

安全设计：
1. 用 SQLite 的只读 URI 打开数据库：file:...?mode=ro
2. 再执行 PRAGMA query_only = ON，双保险。
3. 只执行 SELECT；执行时再包一层 LIMIT 200，防止大结果集。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.shared.config import DB_PATH


def get_readonly_connection() -> sqlite3.Connection:
    """打开只读连接：任何写操作都会被 SQLite 拒绝。"""
    db_uri = f"file:{Path(DB_PATH).as_posix()}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def get_schema() -> dict[str, list[dict]]:
    """
    读取数据库结构。

    返回：
        {
          "sys_user": [{"name": "id", "type": "INTEGER"}, ...],
          ...
        }
    """
    conn = get_readonly_connection()
    try:
        tables = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        schema: dict[str, list[dict]] = {}
        for table in tables:
            table_name = table["name"]
            columns = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
            schema[table_name] = [
                {"name": column["name"], "type": column["type"]}
                for column in columns
            ]
        return schema
    finally:
        conn.close()


def execute_select(sql: str, limit: int = 200) -> tuple[list[str], list[dict]]:
    """
    执行一条 SELECT，返回 (字段名, 行数据)。

    外层再包一层 SELECT * FROM (...) LIMIT 200，
    防止模型生成没有 LIMIT 的大查询。
    """
    conn = get_readonly_connection()
    try:
        wrapped = f"SELECT * FROM ({sql}) LIMIT {limit}"
        cursor = conn.execute(wrapped)
        columns = [item[0] for item in cursor.description] if cursor.description else []
        rows = [dict(row) for row in cursor.fetchall()]
        return columns, rows
    finally:
        conn.close()
