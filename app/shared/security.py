"""
认证与令牌工具（只用标准库，零新增依赖）
================================================
1. 密码：PBKDF2-HMAC-SHA256 + 随机盐
   存储格式：pbkdf2$<迭代次数>$<salt_b64>$<hash_b64>
   校验时重新计算并做「恒定时间比较」，避免时序侧信道。

2. 令牌：HTTPS 场景下等同轻量 JWT
   结构：base64url(payload_json) + "." + base64url(HMAC-SHA256(payload))
   载荷含 uid / role / exp，服务端不存会话（无状态）。

3. 服务令牌：给 Dify 的自定义工具用（写在 .env 的 SERVICE_TOKEN），
   固定值，不参与过期，权限等同管理员，仅限内网使用。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from app.shared.config import SECRET_KEY, TOKEN_TTL_HOURS

PBKDF2_ITERATIONS = 260_000
_ALGO = "pbkdf2"


def _b64e(raw: bytes) -> str:
    """URL 安全的 base64，去掉补位的等号。"""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    """补回等号再解码。"""
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


# ============================================================
# 密码
# ============================================================
def hash_password(password: str) -> str:
    """生成密码哈希。每次调用盐都不同，所以同一密码的哈希不相等。"""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{_ALGO}${PBKDF2_ITERATIONS}${_b64e(salt)}${_b64e(digest)}"


def verify_password(password: str, stored: str) -> bool:
    """
    校验密码。

    兼容历史遗留：如果库里还是占位符 'hash'，一律不通过，
    由启动时的迁移逻辑把它替换成真实哈希。
    """
    if not stored or "$" not in stored:
        return False

    try:
        algo, iterations, salt_text, hash_text = stored.split("$", 3)
        if algo != _ALGO:
            return False
        salt = _b64d(salt_text)
        expected = _b64d(hash_text)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(actual, expected)


def needs_rehash(stored: str) -> bool:
    """占位符或老格式需要重新生成哈希。"""
    return not stored or "$" not in stored or not stored.startswith(f"{_ALGO}${PBKDF2_ITERATIONS}$")


# ============================================================
# 令牌
# ============================================================
def _sign(payload_b64: str) -> str:
    mac = hmac.new(SECRET_KEY.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256)
    return _b64e(mac.digest())


def create_token(uid: int, role: str, username: str, ttl_hours: int | None = None) -> str:
    """签发令牌。role 取值：student / employee / admin / service。"""
    hours = TOKEN_TTL_HOURS if ttl_hours is None else ttl_hours
    payload = {
        "uid": uid,
        "role": role,
        "username": username,
        "exp": int(time.time()) + hours * 3600,
    }
    payload_b64 = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{payload_b64}.{_sign(payload_b64)}"


def decode_token(token: str) -> dict | None:
    """
    校验并解出载荷；签名不对、格式不对、已过期都返回 None。
    """
    if not token or "." not in token:
        return None

    payload_b64, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(_sign(payload_b64), signature):
        return None

    try:
        payload = json.loads(_b64d(payload_b64).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None

    if int(payload.get("exp", 0)) < int(time.time()):
        return None

    return payload
