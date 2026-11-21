"""
NL2SQL 行为测试（不需要真实 API Key）
=====================================
把「调用大模型」这一步替换成假的返回值，验证剩下整条链路：
清洗 SQL -> 安全校验 -> 只读执行 -> 返回结果。

这样即使没有 Key，也能证明代码本身是通的，
答辩被问到「没 Key 你怎么知道能用」时可以直接跑这个。

运行：
    pytest tests/test_nl2sql.py -q
"""

from __future__ import annotations

import pytest

from app.nl2sql.internal import service
from app.nl2sql.schemas import NL2SQLRequest


@pytest.fixture()
def fake_key(monkeypatch):
    """让 resolve_provider 认为已经配好了 Key。"""
    monkeypatch.setattr(service, "resolve_provider", lambda: ("sk-fake", "http://localhost", "fake"))


def _run(question: str) -> dict:
    return service.query(NL2SQLRequest(question=question))


def test_success_path(fake_key, monkeypatch):
    """模型返回合法 SELECT，应当真正查到数据。"""
    monkeypatch.setattr(service, "call_llm", lambda prompt: "SELECT COUNT(*) AS c FROM sys_user;")

    result = _run("一共有多少个用户")

    assert result["attempts"] == 1
    assert result["columns"] == ["c"]
    assert result["rows"][0]["c"] > 0


def test_markdown_code_block_is_cleaned(fake_key, monkeypatch):
    """模型爱用 ```sql 包起来，必须能清洗掉。"""
    monkeypatch.setattr(
        service,
        "call_llm",
        lambda prompt: "```sql\nSELECT real_name FROM sys_user LIMIT 3\n```",
    )

    result = _run("列出几个用户")

    assert result["sql"].lower().startswith("select")
    assert "```" not in result["sql"]
    assert len(result["rows"]) == 3


def test_repair_after_bad_sql(fake_key, monkeypatch):
    """第一次给错字段，应带着报错重试，第二次成功。"""
    answers = iter(["SELECT nope_column FROM sys_user", "SELECT COUNT(*) AS c FROM sys_user"])
    monkeypatch.setattr(service, "call_llm", lambda prompt: next(answers))

    result = _run("一共有多少用户")

    assert result["attempts"] == 2
    assert result["rows"][0]["c"] > 0


def test_reject_non_select(fake_key, monkeypatch):
    """非 SELECT 一律拒绝，重试用尽后报错，绝不落库执行。"""
    monkeypatch.setattr(service, "call_llm", lambda prompt: "DELETE FROM sys_user")

    with pytest.raises(Exception) as exc:
        _run("把所有用户删掉")

    assert "没能生成可执行的 SQL" in str(exc.value)


def test_reject_table_outside_whitelist(fake_key, monkeypatch):
    """查询白名单之外的表（如 sqlite_master）必须拦截。"""
    monkeypatch.setattr(service, "call_llm", lambda prompt: "SELECT name FROM sqlite_master")

    with pytest.raises(Exception) as exc:
        _run("看看数据库里有哪些表")

    assert "没能生成可执行的 SQL" in str(exc.value)


def test_fatal_auth_error_fails_fast(fake_key, monkeypatch):
    """Key 无效时要立刻失败，不能傻等三次重试。"""
    monkeypatch.setattr(service, "NL2SQL_FALLBACK", False)
    calls = {"n": 0}

    def boom(prompt):
        calls["n"] += 1
        raise RuntimeError("Error code: 401 - {'code': 'invalid_api_key'}")

    monkeypatch.setattr(service, "call_llm", boom)

    with pytest.raises(Exception) as exc:
        _run("多少人")

    assert calls["n"] == 1
    assert "Key 无效" in str(exc.value)


def test_fallback_when_quota_exhausted(fake_key, monkeypatch):
    """额度耗尽时，用预置查询兜底，仍然返回真实数据。"""
    monkeypatch.setattr(service, "NL2SQL_FALLBACK", True)

    def boom(prompt):
        raise RuntimeError("403 AllocationQuota.FreeTierOnly: free quota exhausted")

    monkeypatch.setattr(service, "call_llm", boom)

    result = _run("一共有多少个学生")

    assert result["source"] == "fallback"
    assert result["rows"][0]["学生人数"] > 0
    assert "演示降级" in result["message"]
    assert "不是模型生成的" in result["message"]


def test_fallback_can_be_disabled(fake_key, monkeypatch):
    """把 NL2SQL_FALLBACK 设成 0，退化成严格报错。"""
    monkeypatch.setattr(service, "NL2SQL_FALLBACK", False)

    def boom(prompt):
        raise RuntimeError("403 AllocationQuota.FreeTierOnly: free quota exhausted")

    monkeypatch.setattr(service, "call_llm", boom)

    with pytest.raises(Exception) as exc:
        _run("一共有多少个学生")

    assert "免费额度已用完" in str(exc.value)
