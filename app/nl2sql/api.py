"""
NL2SQL 模块的 Module API。

员工 Agent 通过 HTTP 调用；其他 Python 模块如需自然语言查数据，也可走这里。
"""

from __future__ import annotations

from app.nl2sql.internal.service import query

__all__ = ["query"]
