"""
粤教服务智能教育服务助手 · FastAPI 入口

启动方式（在 backend 目录下）：
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

这个文件是“组合根”：
- 负责把各模块的 Router 组装起来；
- 负责全局异常翻译、CORS、启动时建表 / 种子数据；
- 它是唯一允许 import 各模块 internal.router 的地方。
"""

from __future__ import annotations

import hmac
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.catalog.internal.router import router as catalog_router
from app.employee.internal.router import router as employee_router
from app.identity.internal.router import router as identity_router
from app.nl2sql.internal.router import router as nl2sql_router
from app.psych.internal.router import router as psych_router
from app.recommend.internal.router import router as recommend_router
from app.shared.config import SERVICE_TOKEN
from app.shared.deps import is_public
from app.shared.db import init_db, migrate_passwords, seed_if_empty
from app.shared.security import decode_token
from app.shared.errors import DomainError
from app.student.internal.router import router as student_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用启动时：
    1. 执行 schema.sql 建表；
    2. 空库时写入演示数据。

    关闭时不需要额外清理，SQLite 连接都是短连接。
    """
    init_db()
    seed_if_empty()
    # 把历史占位符密码迁移成真实哈希（幂等）
    migrate_passwords()
    yield


app = FastAPI(
    title="粤教服务智能教育服务助手 API",
    description="Dify 负责编排，FastAPI 负责业务能力与数据读写。",
    version="0.1.0",
    lifespan=lifespan,
)

# ============================================================
# 认证中间件
# ------------------------------------------------------------
# 除了 is_public() 列出的端点，其余请求都必须带 Bearer 令牌。
# 放在 CORS 之前注册，保证 CORS 成为外层：401 响应也带跨域头。
# ============================================================
@app.middleware("http")
async def authenticate(request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    if is_public(request.method, request.url.path):
        return await call_next(request)

    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""

    user = None
    if token and SERVICE_TOKEN and hmac.compare_digest(token, SERVICE_TOKEN):
        # Dify 自定义工具用的服务令牌：等同管理员，但不代表某个自然人
        user = {"uid": 0, "role": "admin", "username": "dify-service", "service": True}
    elif token:
        claims = decode_token(token)
        if claims:
            user = {"uid": claims["uid"], "role": claims["role"], "username": claims["username"]}

    if not user:
        return JSONResponse(
            status_code=401,
            content={"detail": "未登录或登录已过期", "code": "unauthorized"},
        )

    request.state.user = user
    return await call_next(request)


# 开发期允许跨域；生产环境建议改成具体域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def handle_domain_error(request, exc: DomainError) -> JSONResponse:
    """
    把 Service 层的领域异常翻译成 HTTP 响应。

    - NotFoundError -> 404
    - ConflictError -> 409
    - BadRequestError -> 400
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


# ============================================================
# 路由注册：每个模块一个前缀
# ============================================================
app.include_router(identity_router, prefix="/api/identity", tags=["身份"])
app.include_router(student_router, prefix="/api/student", tags=["学生事务"])
app.include_router(psych_router, prefix="/api/psych", tags=["心理关怀"])
app.include_router(employee_router, prefix="/api/employee", tags=["员工业务"])
app.include_router(catalog_router, prefix="/api/catalog", tags=["课程与活动"])
app.include_router(recommend_router, prefix="/api/recommend", tags=["画像推荐"])
app.include_router(nl2sql_router, prefix="/api/nl2sql", tags=["NL2SQL"])


@app.get("/api/health", tags=["系统"], summary="健康检查")
def health() -> dict:
    """GET /api/health -> {"status": "ok"}"""
    return {"status": "ok"}


@app.get("/openapi-dify.json", include_in_schema=False)
def openapi_for_dify(request: Request) -> JSONResponse:
    """
    专门给 Dify 用的 OpenAPI schema。

    FastAPI 默认不生成 servers 字段，Dify 解析时会报 KeyError: 'servers'。
    这里根据“当前请求的地址”动态补上：
    - 浏览器访问 localhost:8000 -> servers = http://localhost:8000
    - Dify 容器访问 host.docker.internal:8000 -> servers = http://host.docker.internal:8000
    """
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["servers"] = [{"url": str(request.base_url).rstrip("/")}]

    # 声明 Bearer 认证：Dify 导入时会提示填写「API Key」，
    # 填 .env 里的 SERVICE_TOKEN 即可通过后端鉴权。
    components = schema.setdefault("components", {})
    components["securitySchemes"] = {
        "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "token"}
    }
    schema["security"] = [{"BearerAuth": []}]

    # 公开端点不要求认证（Dify 内部一般也不会调，但保持 schema 准确）
    for path, method in [
        ("/api/health", "get"),
        ("/api/identity/login", "post"),
        ("/api/recommend", "post"),
        ("/api/catalog/projects", "get"),
        ("/api/catalog/events", "get"),
    ]:
        operation = schema.get("paths", {}).get(path, {}).get(method)
        if operation is not None:
            operation["security"] = []

    # ------------------------------------------------------------
    # 最小权限：Dify 专用 schema 里剔除「修改 / 删除」类接口。
    # ------------------------------------------------------------
    # 原因：Dify 用的是 SERVICE_TOKEN（等同管理员），一旦这些接口出现在 schema 里，
    # 导入后 Agent 就能调用，可能误改 / 误删业务数据。CRUD 补全的改删接口只给
    # 前端管理后台（真人操作）用，不从 Dify 暴露。前端仍通过普通 /openapi.json + 用户登录令牌调用。
    #
    # 注意：这里只影响 Dify 导入用的这份 schema，不影响真实路由，也不影响前端。
    # 前端调用走的是各自接口 + 真人登录令牌，鉴权在 main.py 中间件按角色放行。
    _DIFY_HIDDEN = {
        ("/api/student/scores/{score_id}", "patch"),
        ("/api/student/scores/{score_id}", "delete"),
        # 撤销售后工单是删除操作，只给前端真人，不给 Dify 智能体
        ("/api/student/feedback/{ticket_id}", "delete"),
        ("/api/employee/leads/{lead_id}", "patch"),
        ("/api/employee/leads/{lead_id}", "delete"),
        ("/api/employee/reports/{report_id}", "patch"),
        ("/api/employee/reports/{report_id}", "delete"),
        ("/api/catalog/registrations/{registration_id}/cancel", "post"),
        # 新增活动 / 项目同样是写操作，只给前端管理后台真人用，不对 Dify 暴露
        ("/api/catalog/events", "post"),
        ("/api/catalog/projects", "post"),
    }
    paths = schema.get("paths", {})
    for path, method in _DIFY_HIDDEN:
        operation = paths.get(path, {}).get(method)
        if operation is not None:
            del paths[path][method]
        # 若该路径下已无任何方法，整条移除，避免 Dify 导入空路径
        if path in paths and not paths[path]:
            del paths[path]

    return JSONResponse(schema)
