# 粤教服务 · 多智能体留学服务系统

Dify 负责「大脑」（Agent 编排、知识库、意图识别），FastAPI 负责「手脚」（业务规则、SQLite 读写），React + Vite 负责「界面」（官网 + 三身份工作台）。

## 1. 目录

```
.
├── app/                        # 后端：FastAPI 应用
│   ├── main.py                 # 组合根：注册路由、异常、CORS、启动建表
│   ├── shared/                 # 配置、数据库、异常
│   ├── identity/               # 用户 / 角色
│   ├── student/                # 请假 / 售后 / 成绩
│   ├── psych/                  # 情绪 / 画像 / 预警 / 对话
│   ├── employee/               # CRM 线索 / 日报
│   ├── catalog/                # 课程 / 活动 / 报名
│   ├── recommend/              # 画像研判 / 推荐
│   └── nl2sql/                 # 自然语言转 SQL（只读）
├── schema.sql                  # 12 张表
├── requirements.txt
├── .env.example
├── AGENTS.md                   # 架构规范
├── tests/test_architecture.py  # 架构测试
└── frontend/                   # 前端：液态玻璃官网 + 工作台（React 19 + Vite）
    ├── src/                    # Site.jsx / panels.jsx / LoginDialog.jsx / config.js
    ├── public/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── .env.example            # Dify Key 模板（复制为 .env.local 再填）
    └── .gitignore
```

每个模块内部：

```
<module>/
├── api.py          # 对外能力（其他模块只能 import 这个）
├── schemas.py      # Pydantic 入参/出参
└── internal/
    ├── router.py   # Controller
    ├── service.py  # 业务规则
    └── repository.py # SQL
```

## 2. 准备环境

需要 Python 3.10+。

```powershell
cd C:\Users\Windows\Desktop\1117项目\backend

# 创建虚拟环境
python -m venv .venv

# 激活（PowerShell）
.\.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt
```

> 如果 PowerShell 提示“禁止运行脚本”，先执行：
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## 3. 配置环境变量

```powershell
Copy-Item .env.example .env
notepad .env
```

至少填：
```env
# 二选一：百炼（千问）或 DeepSeek
NL2SQL_PROVIDER=dashscope
DASHSCOPE_API_KEY=你的百炼 API Key
# NL2SQL_PROVIDER=deepseek
# DEEPSEEK_API_KEY=你的 DeepSeek Key
```

不填也能启动，只是 `/api/nl2sql/query` 会返回 400「未配置 Key」；
Key 填了但无效 / 额度耗尽时返回 **503**，`detail` 里会写明具体原因（不会假装成功）。

## 4. 启动

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- 接口文档：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/api/health>
- OpenAPI：<http://localhost:8000/openapi.json>

第一次启动会自动：
1. 执行 `schema.sql` 建 12 张表；
2. 写入演示用户、课程、活动、客户线索、成绩。

## 5. 接口清单

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/identity/users/{user_id}` | 按编号查用户 |
| GET | `/api/identity/students` | 查学生列表 |
| GET | `/api/identity/employees` | 查员工列表 |
| POST | `/api/student/leaves` | 提交请假 |
| GET | `/api/student/leaves` | 查请假记录 |
| POST | `/api/student/leaves/{id}/approve` | 审批请假 |
| POST | `/api/student/feedback` | 提交售后反馈 |
| GET | `/api/student/feedback` | 查售后工单 |
| POST | `/api/student/feedback/{id}/resolve` | 解决工单 |
| GET | `/api/student/scores` | 查成绩（可按学生 / 课程过滤） |
| POST | `/api/student/scores` | 录入成绩 |
| PATCH | `/api/student/scores/{score_id}` | 修改成绩（只改传了的字段） |
| DELETE | `/api/student/scores/{score_id}` | 删除成绩 |
| POST | `/api/psych/assess` | 情绪评估 + 预警 |
| GET | `/api/psych/profile/{student_id}` | 查心理画像 |
| GET | `/api/psych/alerts` | 查预警列表 |
| PATCH | `/api/psych/alerts/{id}` | 更新预警状态 |
| POST | `/api/psych/conversations` | 写对话记录 |
| GET | `/api/psych/conversations` | 查对话记录（学生看自己，员工可查任意用户） |
| POST | `/api/employee/leads` | 录入客户线索 |
| GET | `/api/employee/leads` | 查客户线索 |
| PATCH | `/api/employee/leads/{id}` | 编辑客户资料（不含状态 / 负责人） |
| DELETE | `/api/employee/leads/{id}` | 删除客户线索（已签约禁止删，返回 409） |
| PATCH | `/api/employee/leads/{id}/status` | 更新客户状态 |
| POST | `/api/employee/reports` | 提交日报 |
| GET | `/api/employee/reports` | 查日报 |
| PATCH | `/api/employee/reports/{id}` | 修改日报 |
| DELETE | `/api/employee/reports/{id}` | 删除日报 |
| GET | `/api/catalog/projects` | 查课程 / 项目（已包含详情字段） |
| POST | `/api/catalog/projects` | 新增项目（仅员工/管理员，真人操作） |
| GET | `/api/catalog/events` | 查活动 |
| POST | `/api/catalog/events` | 新增活动（仅员工/管理员，真人操作） |
| POST | `/api/catalog/events/{id}/register` | 活动报名 |
| GET | `/api/catalog/registrations` | 查报名记录 |
| POST | `/api/catalog/registrations/{id}/cancel` | 取消报名（软删除，回滚活动人数） |
| POST | `/api/recommend` | 画像推荐 |
| POST | `/api/nl2sql/query` | 自然语言查数据 |

> **CRUD 补全说明（2026-11-18）**：以上 PATCH / DELETE / 取消 / 对话查询为补齐的缺口接口，
> 均未改表结构。两个安全约定：①删除已签约线索会被拒绝（409），防止关联的学生账号 / 选课悬空，
> 要终止合作请改「已流失」；②取消报名是软删除（status 改「已取消」并回滚人数），重复取消返回 409。
> 成绩 / 日报的 PATCH 只改传了的字段，一个都不传返回 400。
>
> **新增活动 / 项目（2026-11-18 补）**：`POST /api/catalog/events`、`POST /api/catalog/projects`
> 只给前端管理后台真人用（require_staff 鉴权，学生 403、匿名 401），已从 Dify 专用 schema 隐藏。
> 活动时间统一规范化为 `年-月-日 时:分:秒`（接受 ISO 的 T 分隔输入），名称纯空白返回 400。

## 5.1 Swagger 测试注意

- **请假**：只填 `student_id` + `reason`。
  - 不要把请假事由填进 `service_type`（它只接受“请假 / 考务查询”）；
  - 不要手动填 `start_time` / `end_time`，留空后后端会从 `reason` 里解析“今天 / 明天 / 后天 / 半天 / 一天”。
- **情绪评估**：手工测试只填 `student_id` + `text`。
  - `emotion_score` / `emotion_tag` 是给 Dify 传大模型结果用的，留空才会走关键词判断；
  - 如果文本里有明确关键词（开心 / 抑郁 / 不想活），以关键词为准，避免上游误传分数。
- 请假起止时间填成同一个，会返回 **422**，这是故意的校验。

## 6. 运行测试

```powershell
pytest tests/test_architecture.py -q
```

## 7. 接入 Dify

Dify 的「自定义工具」支持导入 OpenAPI：

```
http://host.docker.internal:8000/openapi.json
```

> Dify 跑在 Docker 里，`localhost` 指容器自己；
> 用 `host.docker.internal` 访问 Windows 主机。
> 后端必须监听 `0.0.0.0`。

导入后，每个接口会变成一个工具，Agent 就能调用请假、查客户、NL2SQL 等能力。

## 8. 注意

- `schema.sql` 里的 `password_hash` 只是演示占位，生产必须用 bcrypt / Argon2。
- SQLite 适合演示；真实生产建议换 MySQL / PostgreSQL。
- NL2SQL 只读、只允许 SELECT、表白名单、限 200 行；不要把它改成可写。
- 不要把 `.env` 提交到 Git。
