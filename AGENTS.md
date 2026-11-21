# AGENTS.md · 粤教服务后端架构规范

> 给 AI 开发助手（以及人类开发者）看的硬规则。
> 新功能先读这一页，再动手。

## 1. 架构一句话

**自治业务模块 + 模块内轻量三层 + 可执行架构约束 + 按需领域建模。**

- 业务能力按模块纵向切分；
- 模块内部：`router -> service -> repository`；
- 跨模块只走对方的 `api.py`；
- 架构规则由 `tests/test_architecture.py` 自动检查。

## 2. 模块与数据所有权

| 模块 | 职责 | 拥有的表 |
|---|---|---|
| `identity` | 用户、角色 | `sys_user` |
| `student` | 请假、售后、成绩 | `student_admin_service`、`student_feedback_ticket`、`student_score` |
| `psych` | 情绪、画像、预警、对话 | `student_psych_profile`、`student_psych_alert`、`conversation_log` |
| `employee` | CRM 线索、日报 | `crm_lead`、`employee_daily_report` |
| `catalog` | 课程/项目、活动、报名 | `course_project`、`event_lecture`、`event_registration` |
| `recommend` | 画像研判与推荐 | 无（读 `catalog`） |
| `nl2sql` | 自然语言查询（只读） | 无（只读数据库） |

## 3. 目录结构

```
app/<module>/
├── api.py              # 对外能力（其他模块只能 import 这个）
├── schemas.py          # 公开 DTO
└── internal/
    ├── router.py       # Controller：HTTP 入参/出参
    ├── service.py      # 业务规则
    └── repository.py   # SQL / 数据访问
```

## 4. 五条硬规则

1. **跨模块只能 import `<module>.api`**，禁止 import 其他模块的 `internal`。
2. **只有 Service 层可以发起跨模块调用**；`router` 不直接调别的模块。
3. **依赖方向**：`router -> service -> repository`；`repository` 不反向依赖 `service` / `router`。
4. **禁止循环依赖**：模块依赖图必须是 DAG（有向无环图）。
5. **`shared/` 不 import 任何业务模块**，它只提供配置、数据库、异常。

## 5. 写代码的约定

- 业务异常用 `shared/errors.py` 里的 `DomainError` 子类，不抛 `HTTPException`。
- 所有 SQL 放在对应模块的 `repository.py`，不写在 `router` / `service` 里。
- 时间统一用 `YYYY-MM-DD HH:MM:SS` 字符串。
- 密码字段只做演示，生产必须换成 bcrypt / Argon2。
- 新增字段先改 `schema.sql`，再改 repository / schemas / service。

## 6. 完成定义（DoD）

- `pytest tests/test_architecture.py -q` 通过；
- `/docs` 能看到新接口；
- 新接口的入参/出参有 Pydantic 模型；
- 更新了本文件或 README 中的接口说明（如有必要）。
