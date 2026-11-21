"""
全局配置模块
------------
集中读取环境变量和路径，避免在业务代码里散落 os.getenv / 硬编码路径。

约定：
- backend/.env        本地环境变量（不进 Git）
- backend/schema.sql  12 张表的建表脚本
- backend/yuejiao.db  SQLite 数据库文件（第一次启动自动创建）
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

# config.py 位于 backend/app/shared/config.py
# BASE_DIR = backend/app
# PROJECT_DIR = backend
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BASE_DIR.parent

# 读取 backend/.env；不存在时使用系统环境变量
load_dotenv(PROJECT_DIR / ".env")

# SQLite 数据库文件路径；默认放在 backend/yuejiao.db
DB_PATH = os.getenv("DB_PATH", str(PROJECT_DIR / "yuejiao.db"))

# 建表脚本路径
SCHEMA_PATH = PROJECT_DIR / "schema.sql"

# ------------------------------------------------------------
# NL2SQL 用的大模型配置
# ------------------------------------------------------------
# 供应商四选一：
#   dashscope（阿里云百炼 / 通义千问）
#   deepseek （DeepSeek 官方）
#   zhipu    （智谱 GLM，glm-4-flash 永久免费）
#   custom   （任意 OpenAI 兼容端点，自己填 NL2SQL_API_KEY / BASE_URL / MODEL）
# 换供应商只需要改 NL2SQL_PROVIDER，不用动代码。
NL2SQL_PROVIDER = os.getenv("NL2SQL_PROVIDER", "dashscope").strip().lower()

# 阿里云百炼（通义千问）
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# DeepSeek（OpenAI 兼容接口）
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

# 智谱 GLM：glm-4-flash 永久免费，每天 100 万 token，最适合当兜底
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "")
ZHIPU_BASE_URL = os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")

# 自定义端点（任何 OpenAI 兼容服务：硅基流动、火山方舟、本地 Ollama 等）
NL2SQL_API_KEY = os.getenv("NL2SQL_API_KEY", "")
NL2SQL_BASE_URL = os.getenv("NL2SQL_BASE_URL", "")

NL2SQL_MODEL = os.getenv("NL2SQL_MODEL", "qwen-plus")

# 演示降级（默认关闭，不要随便开）：
# 模型不可用时用预置 SQL 兜底。关键词匹配会误判问法（例如「各班平均分」
# 可能被匹配成「学生人数」），返回错误答案，答辩时风险很大。
# 只有当你明确知道演示问题都在预置清单里时，才设成 1。
NL2SQL_FALLBACK = os.getenv("NL2SQL_FALLBACK", "0") == "1"

# 单次调用模型的超时（秒）。Dify 自定义工具默认 30~60 秒就判超时，
# 所以这里不能设太大，否则后端还在跑、Dify 已经报失败了。
NL2SQL_TIMEOUT = float(os.getenv("NL2SQL_TIMEOUT", "20"))
# 整个请求的总时间预算（秒）：到达后不再重试，直接返回最后一次错误。
NL2SQL_TIME_BUDGET = float(os.getenv("NL2SQL_TIME_BUDGET", "40"))

# ============================================================
# 认证配置
# ============================================================
# 令牌签名密钥：正式环境必须在 .env 里设置成随机长字符串。
# 没设置时自动生成一个（重启失效，仅够本地演示）。
SECRET_KEY = os.getenv("SECRET_KEY", "") or secrets.token_urlsafe(48)

# 令牌有效期（小时）
TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", "12"))

# 服务令牌：给 Dify 的自定义工具调用后端用。
# 为空则不启用服务令牌（Dify 工具会因未认证失败）。
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "").strip()

# 演示默认口令：仅用于把种子数据的占位哈希迁成真实哈希
DEFAULT_DEMO_PASSWORD = os.getenv("DEFAULT_DEMO_PASSWORD", "123456")
