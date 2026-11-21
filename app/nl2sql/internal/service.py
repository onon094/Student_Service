"""
NL2SQL 模块的 Service（业务层）。

流程：
1. 读取数据库 Schema；
2. 把 Schema + 表关系 + 用户问题拼成 Prompt（提示词）；
3. 调用千问（OpenAI 兼容接口）生成 SQL；
4. 清洗 SQL；
5. 安全校验：只允许 SELECT、单语句、表白名单；
6. 只读执行；
7. 失败时把“问题 + 错误 SQL + 数据库报错 + Schema”再交给模型修复，最多 3 次。
"""

from __future__ import annotations

import re
import time

from app.nl2sql.schemas import NL2SQLRequest
from app.shared.config import (
    DASHSCOPE_API_KEY,
    DASHSCOPE_BASE_URL,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    NL2SQL_API_KEY,
    NL2SQL_BASE_URL,
    NL2SQL_MODEL,
    NL2SQL_FALLBACK,
    NL2SQL_PROVIDER,
    NL2SQL_TIME_BUDGET,
    NL2SQL_TIMEOUT,
    ZHIPU_API_KEY,
    ZHIPU_BASE_URL,
)
from app.shared.errors import BadRequestError, DomainError

from . import repository

# 表之间最重要的关联关系，写进 Prompt 帮模型正确 JOIN
RELATIONSHIPS = """
sys_user.id = student_admin_service.student_id
sys_user.id = student_feedback_ticket.student_id
sys_user.id = student_score.student_id
sys_user.id = student_psych_profile.student_id
sys_user.id = student_psych_alert.student_id
sys_user.id = conversation_log.user_id
sys_user.id = crm_lead.owner_employee_id
sys_user.id = employee_daily_report.employee_id
sys_user.id = student_enrollment.student_id
crm_lead.id = event_registration.customer_id
event_lecture.id = event_registration.event_id
course_project.id = student_enrollment.project_id
"""

# ============================================================
# 业务术语映射：把用户嘴里的词，翻译成数据库里的表和字段。
# ------------------------------------------------------------
# 这段是让小模型也能答对的关键。没有它，模型会把「学生」误解成
# student_enrollment（只有已签约的 4 人），而不是 sys_user 里的 8 人；
# 也会把「班级」当成不存在的字段。答辩讲 Prompt 设计时，这是重点。
# ============================================================
BUSINESS_RULES = """
【业务术语 → 表 / 字段 对照表】（非常重要，必须遵守）
- 「学生」「学员」「多少人」→ sys_user 表，且必须加条件 user_type = 'STUDENT'。
  不要把「学生」理解成 student_enrollment（那只是已签约报课的学生，不是全部）。
- 「班级」「班」→ sys_user.department 字段（例如「新加坡本科班」）。
- 「姓名」「叫什么」→ sys_user.real_name（不是 username，那是登录账号）。
- 「员工」「老师」「顾问」→ sys_user 表，user_type = 'EMPLOYEE'。
- 「成绩」「分数」→ student_score.score；按班级统计要 JOIN sys_user 拿 department。
- 【课程分两类，务必分清，不要混为一谈】
  * 「课程」「科目」「考了哪几门」→ 指考试科目，字段是 student_score.course_name。
    真实科目用 SELECT DISTINCT course_name FROM student_score 查，不要凭空列、不要编数字。
    （当前真实科目：Mysql、Python、liunx、学术英语、德语、数学、英语、雅思）
  * 「招生项目」「专业」「报读项目」「报什么班」→ 指留学项目，字段是 course_project.project_name。
    真实项目用 SELECT project_name, category FROM course_project 查。
    （如 2+2 新加坡定向培养本科班、德国双元制）
  * 注意：「课程/科目」是考试分数那一类（Python/英语/数学…）；
    「项目/专业/班」是留学招生项目（新加坡本科班/德国双元制…）。是两种不同的东西。
  * 【默认判定】用户只说「课程」两个字（如「几门课程」「有哪些课程」「考了哪些课程」），
    一律当成考试科目，查 student_score.course_name，绝不查 course_project。
    只有当问题里明确出现「招生 / 报读 / 专业 / 项目 / 报什么班 / 留学项目」这些词时，才用 course_project。
  * 「一共有几门课程」必须写 DISTINCT 计数，不能数学生、不能数签约记录：
    SELECT COUNT(DISTINCT course_name) FROM student_score
- 【不存在的字段，禁止编造，必须如实告知】
  * 本系统【没有"性别"字段】，也没有"年龄"字段。用户问「男生/女生有几个」「男女比例」
    「多少人男性」等按性别统计的问题时，不要生成任何 SQL，直接在 message 里如实说明：
    "数据库没有记录学员性别，无法按性别统计"。绝对不要从 real_name 猜性别、
    不要用 real_name LIKE（如把"女"当姓名匹配），这是编造。
  * 凡是用户要查的字段在表结构里不存在（如性别、年龄、国籍、身份证号），
    一律不生成 SQL，如实说明该信息系统未记录。
- 【"我的/本人"的归属】员工助手里用户说「我的日报」「我的客户」「我负责的」时，
  "我"指当前登录员工。问题文本里若带"当前用户 XXX"标注（Dify 传入的登录账号，
  如 teacher_chen / 陈老师），必须用它关联 sys_user.id 再查对应 employee_id / owner_employee_id，
  账号和真实姓名都可以匹配：WHERE u.username = 'XXX' OR u.real_name = 'XXX'。
  例如"查询我的日报"+标注"当前用户 teacher_chen"：
  SELECT r.report_date, r.content FROM employee_daily_report r
  JOIN sys_user u ON u.id = r.employee_id
  WHERE u.username = 'teacher_chen' OR u.real_name = 'teacher_chen'
  ORDER BY r.report_date DESC
  注意：绝不能把"我"字当字面值去查（如 WHERE real_name LIKE '%我%'），那一定查不到。
  若没有任何用户标注，就在 message 里说明"无法确定当前用户，请说明具体姓名"，不要瞎猜。
- 「客户」「线索」→ crm_lead 表；「跟进记录」→ crm_lead.follow_up_history。
  * 「查一下某人的跟进记录 / 客户档案」（如「查一下许同学的跟进记录」）→
    这个人一般指【客户本人】，直接按 crm_lead.customer_name 过滤，查该行的
    customer_name / background_info / follow_up_history / status 等字段。
    不要 JOIN sys_user 把人名当成员工（owner_employee_id），那是负责员工，不是客户。
    标准写法：SELECT customer_name, background_info, follow_up_history, status
              FROM crm_lead WHERE customer_name LIKE '%许同学%'
- 「预警」「心理风险」→ student_psych_alert；风险等级字段是 risk_level。
- 「签约」「报课」「开通课程」→ student_enrollment，开通的项目名是 project_name。
- 「请假」→ student_admin_service；「工单/投诉/售后」→ student_feedback_ticket。
- 「活动」「讲座」→ event_lecture；报名记录 → event_registration。

【容易答错的场景，照着写】
- 「一共有多少个学生」应写：
  SELECT COUNT(*) FROM sys_user WHERE user_type = 'STUDENT'
- 「各班级的平均分」应 JOIN sys_user 取 department 分组，不是按 student_id 分组：
  SELECT u.department, ROUND(AVG(s.score),1) AS avg_score
  FROM student_score s JOIN sys_user u ON u.id = s.student_id
  WHERE u.user_type = 'STUDENT' GROUP BY u.department
- 显示学生相关信息时，尽量带上 real_name 姓名，不要只给 student_id 学号。
- 「有哪些 / 列出 / 多少个 / 共几门」这类清单或计数问题，必须用 SQL 查真实数据，
  禁止凭印象回答固定数字或固定名单（例如不许直接说「共 3 门课程」）。
  * 「有几门课程 / 有哪些课程 / 考了哪些科目」→ 查考试科目：
    SELECT DISTINCT course_name FROM student_score ORDER BY course_name
  * 「有几个招生项目 / 有哪些专业」→ 查项目表：
    SELECT project_name, category FROM course_project
  先判断用户问的是「考试科目」还是「招生项目」，再选对应的表。
"""

# 危险关键字：出现在 SQL 里直接拒绝
DANGEROUS_KEYWORDS = [
    "insert", "update", "delete", "drop", "alter", "create",
    "replace", "truncate", "attach", "detach", "pragma", "vacuum",
    "reindex", "grant", "revoke",
]

# ============================================================
# 演示降级用的「常见问题 → 固定 SQL」
# ------------------------------------------------------------
# 用途：模型的 Key 失效 / 免费额度耗尽 / 断网时，答辩现场仍然能
#       演示「自然语言 → SQL → 结果表格」这条完整链路。
# 注意：这里只放只读 SELECT，和 validate_sql 的安全规则一致；
#       主路径仍然是大模型生成 SQL，降级只在模型不可用时触发，
#       返回值里会明确标 source="fallback"，不会假装是模型生成的。
# ============================================================
FALLBACK_RULES: list[tuple[str, str, str]] = [
    (
        r"(多少|总共|一共|几个|人数).*(学生)|(学生).*(多少|总共|一共|几个|人数)",
        'SELECT COUNT(*) AS "学生人数" FROM sys_user WHERE upper(user_type) = \'STUDENT\'',
        "学生总人数",
    ),
    (
        r"(每个|各).*(学生|人).*(预警|报警)|预警.*(几次|次数|统计)",
        'SELECT u.real_name AS "学生", COUNT(a.id) AS "预警次数" '
        "FROM sys_user u LEFT JOIN student_psych_alert a ON a.student_id = u.id "
        "WHERE upper(u.user_type) = 'STUDENT' GROUP BY u.id ORDER BY \"预警次数\" DESC",
        "每个学生被预警的次数",
    ),
    (
        r"预警|心理.*风险|风险等级",
        'SELECT risk_level AS "风险等级", COUNT(*) AS "数量" '
        "FROM student_psych_alert GROUP BY risk_level",
        "心理预警分布",
    ),
    (
        r"平均|班级.*分|成绩.*平均",
        'SELECT COALESCE(u.department, \'未分班\') AS "班级", '
        'ROUND(AVG(s.score), 1) AS "平均分", COUNT(*) AS "考试人次" '
        "FROM student_score s JOIN sys_user u ON u.id = s.student_id "
        'GROUP BY "班级"',
        "各班级平均分",
    ),
    (
        r"成绩|分数|考了",
        'SELECT u.real_name AS "学生", s.course_name AS "课程", '
        's.score AS "分数", s.semester AS "学期" '
        "FROM student_score s JOIN sys_user u ON u.id = s.student_id "
        "ORDER BY s.score DESC LIMIT 50",
        "学生成绩明细",
    ),
    (
        r"(线索|客户).*(多少|总共|一共|几条|几人)|多少.*(线索|客户)",
        'SELECT COUNT(*) AS "线索总数" FROM crm_lead',
        "客户线索总数",
    ),
    (
        r"线索|客户|意向|跟进",
        'SELECT customer_name AS "客户", status AS "状态", '
        'contact_info AS "联系方式", follow_up_history AS "跟进记录" '
        "FROM crm_lead ORDER BY id DESC LIMIT 50",
        "客户线索与跟进记录",
    ),
    (
        r"请假|审批",
        'SELECT u.real_name AS "学生", t.service_type AS "类型", '
        't.status AS "状态", t.start_time AS "开始时间" '
        "FROM student_admin_service t JOIN sys_user u ON u.id = t.student_id "
        "ORDER BY t.id DESC LIMIT 50",
        "请假审批记录",
    ),
    (
        r"日报|工作汇报",
        'SELECT u.real_name AS "员工", r.report_date AS "日期", '
        'r.content AS "内容" '
        "FROM employee_daily_report r JOIN sys_user u ON u.id = r.employee_id "
        "ORDER BY r.report_date DESC LIMIT 50",
        "员工日报",
    ),
    (
        r"报名|活动|讲座",
        'SELECT e.event_name AS "活动", COUNT(g.id) AS "报名人数" '
        "FROM event_registration g JOIN event_lecture e ON e.id = g.event_id "
        'GROUP BY e.event_name',
        "活动报名人数",
    ),
    (
        r"签约|已报|开通.*课程|报读",
        'SELECT u.real_name AS "学生", e.project_name AS "已报项目", '
        'e.status AS "状态", e.signed_at AS "签约时间" '
        "FROM student_enrollment e JOIN sys_user u ON u.id = e.student_id "
        "ORDER BY e.signed_at DESC",
        "学生签约与开课情况",
    ),
    (
        # ACC-008 降级也要和主路径口径一致：「课程/科目」= 考试科目，不是招生项目
        r"(几门|哪些|列出|所有).*(课程|科目)|(课程|科目).*(几门|哪些|有哪些)",
        'SELECT DISTINCT course_name AS "课程" FROM student_score ORDER BY "课程"',
        "考试科目清单",
    ),
    (
        r"招生项目|有哪些项目|报读项目|专业",
        'SELECT project_name AS "项目", category AS "类别", '
        'target_audience AS "适配人群" FROM course_project',
        "招生项目清单",
    ),
    (
        r"工单|投诉|售后|反馈",
        'SELECT status AS "状态", COUNT(*) AS "数量" '
        "FROM student_feedback_ticket GROUP BY status",
        "售后工单分布",
    ),
]


def fallback_sql(question: str) -> tuple[str, str] | None:
    """
    按关键词匹配预置查询，返回 (SQL, 说明)。

    匹配不到就返回 None，由调用方决定报错还是继续。
    """
    for pattern, sql, note in FALLBACK_RULES:
        if re.search(pattern, question, flags=re.IGNORECASE):
            return sql, note
    return None


# 表名自带误导：course_project 名字里有 course，但存的是「招生项目」；
# 真正的「考试科目」在 student_score.course_name。小模型会被表名带偏，
# 所以在表结构描述里加中文注解，明确每张表的业务含义（上下文最近的证据）。
TABLE_NOTES = {
    "course_project": "招生项目表（存 2+2本科班、德国双元制等留学项目；不是考试科目！）",
    "student_score": "学生成绩表；其中 course_name 才是「考试科目」（Python、英语、数学等）",
}


def schema_to_text(schema: dict[str, list[dict]]) -> str:
    """把 Schema 字典转成适合放进 Prompt 的文本。"""
    lines: list[str] = []
    for table, columns in schema.items():
        note = TABLE_NOTES.get(table)
        lines.append(f"表：{table}" + (f"  —— {note}" if note else ""))
        for column in columns:
            lines.append(f"  - {column['name']} {column['type']}")
        lines.append("")
    return "\n".join(lines)


def detect_course_intent(question: str) -> str:
    """
    判断用户问的「课程」是哪一类，返回一句近距离强提示，贴在问题正下方。

    背景：免费小模型对中文「课程」有很强的固有理解，会固执地查 course_project，
    把规则写在 Prompt 中段压不住。所以把判定结论放在问题正下方（模型最重视的位置）。
    注意：这是提示词引导，不是替模型写死答案，SQL 仍由模型生成。
    """
    q = question
    # 明确的招生/报读语义 → 招生项目表
    if any(w in q for w in ("招生", "报读", "专业", "报什么班", "留学项目", "培养班", "本硕", "专升")):
        return "【本题判定】用户问的是「招生项目/专业」，请查 course_project.project_name，不要用 student_score。"
    # 只要提到课程/科目/考了什么 → 考试科目
    if any(w in q for w in ("课程", "科目", "考了", "成绩单", "几门")):
        return (
            "【本题判定】用户问的是「考试科目」，只查 student_score.course_name，"
            "严禁用 course_project（那是招生项目，不是考试科目）。"
            "标准写法：SELECT COUNT(DISTINCT course_name) FROM student_score（计数）"
            "或 SELECT DISTINCT course_name FROM student_score ORDER BY course_name（列清单）。"
        )
    return ""


def detect_unsupported_field(question: str) -> str | None:
    """
    识别用户问了数据库根本没记录的字段。
    这类问题不能翻译 SQL（模型会把"女"当姓名查，产生幻觉），
    直接返回如实说明，从源头杜绝编造。
    """
    q = question or ""
    # 性别统计：本库 sys_user 没有 gender 字段
    if re.search(r"(男生|女生|男|女|性别|男女)", q) and re.search(
        r"(几个|多少|人数|比例|统计|各|分别|有多少|数量)", q
    ):
        return "数据库没有记录学员性别，无法按性别统计。"
    # 年龄统计：同样没有 age 字段
    if re.search(r"年龄", q) and re.search(r"(几个|多少|平均|统计|多大|分布)", q):
        return "数据库没有记录学员年龄，无法按年龄统计。"
    return None


def build_prompt(question: str, schema_text: str) -> str:
    """首次生成 SQL 的 Prompt。"""
    # 把课程判定结论贴在问题正下方，近距离引导模型（位置越近，权重越高）
    intent_hint = detect_course_intent(question)
    intent_block = f"\n{intent_hint}\n" if intent_hint else ""

    return f"""你是 SQLite SQL 专家。数据库表结构如下：
{schema_text}

表关系：
{RELATIONSHIPS}
{BUSINESS_RULES}
用户问题：{question}
{intent_block}
要求：
1. 只返回一条 SELECT 语句，不要解释，不要 markdown 代码块。
2. 只使用上面存在的表和字段，不要编造。
3. 严格按上面的「业务术语对照表」选择表和字段，尤其注意「学生」用的是 sys_user。
4. 禁止 INSERT / UPDATE / DELETE / DROP / ALTER / CREATE / PRAGMA / ATTACH。
5. 结果最多 200 行。
"""


def fix_prompt(question: str, bad_sql: str, error: str, schema_text: str) -> str:
    """SQL 执行失败时，把错误信息带回给模型，让它修复。"""
    return f"""你是 SQL 调试专家。用户问题：
{question}

你上一次生成的 SQL：
{bad_sql}

数据库报错：
{error}

数据库表结构：
{schema_text}
{BUSINESS_RULES}
请修复 SQL。要求：
1. 只返回一条 SELECT 语句，不要解释。
2. 只使用 Schema 中存在的表和字段，并遵守业务术语对照表。
3. 必须修正上面的报错，不要重复同样的错误。
"""


# 供应商的中文名（报错时告诉用户是哪家出的问题）与默认模型
PROVIDER_LABEL = {
    "dashscope": "阿里云百炼（通义千问）",
    "deepseek": "DeepSeek",
    "zhipu": "智谱 GLM",
    "custom": "自定义端点",
}
PROVIDER_DEFAULT_MODEL = {
    "dashscope": "qwen-plus",
    "deepseek": "deepseek-chat",
    "zhipu": "glm-4-flash",
}


def resolve_provider() -> tuple[str, str, str]:
    """
    根据 NL2SQL_PROVIDER 选择模型供应商。

    返回 (api_key, base_url, model)。
    这四家都提供 OpenAI 兼容接口，所以 call_llm 的代码完全一样。
    """
    provider = NL2SQL_PROVIDER
    # 只改了供应商、没改模型名时，自动换成该家的默认模型，
    # 避免出现「拿 qwen-plus 去调 DeepSeek」这种必然失败的情况。
    model = NL2SQL_MODEL or PROVIDER_DEFAULT_MODEL.get(provider, "qwen-plus")
    if provider != "dashscope" and "qwen" in model.lower():
        model = PROVIDER_DEFAULT_MODEL.get(provider, model)

    if provider == "deepseek":
        return DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, model
    if provider == "zhipu":
        return ZHIPU_API_KEY, ZHIPU_BASE_URL, model
    if provider == "custom":
        return NL2SQL_API_KEY, NL2SQL_BASE_URL, model
    return DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, model


# 这类错误重试没有意义：Key 错了、没额度、没权限、连不上。
# 必须立刻告诉用户，而不是换个 SQL 再试三次。
# 注意顺序：先匹配「具体业务码」，最后才匹配裸的 401/403/429，
# 否则 403 + FreeTierOnly 会被误判成「没有权限」。
_FATAL_PATTERNS = (
    ("freetieronly", "免费额度已用完。请到控制台关闭「仅使用免费额度」模式并充值，或换一家供应商"),
    ("free quota", "免费额度已用完。请换一家供应商，或在控制台充值"),
    ("quota exhausted", "调用额度已用完。请换一家供应商，或在控制台充值"),
    ("allocationquota", "调用额度已用完。请换一家供应商，或在控制台充值"),
    ("arrearage", "账号欠费，模型服务已停用"),
    ("insufficient", "账户余额不足"),
    ("invalid_api_key", "API Key 无效（可能被删除，或复制时漏了字符）"),
    ("incorrect api key", "API Key 无效（可能被删除，或复制时漏了字符）"),
    ("invalidapikey", "API Key 无效（可能被删除，或复制时漏了字符）"),
    ("access denied", "当前 Key 没有该模型的调用权限，请确认已开通这个模型"),
    ("throttl", "调用太频繁被限流了，等几秒再试"),
    ("rate limit", "调用太频繁被限流了，等几秒再试"),
    ("timeout", "连接模型服务超时（检查网络或代理）"),
    ("timed out", "连接模型服务超时（检查网络或代理）"),
    ("connection", "连不上模型服务（检查网络或代理）"),
    ("401", "API Key 无效或已过期"),
    ("403", "没有调用权限（Key 无效、模型未开通，或额度已用完）"),
    ("429", "调用太频繁或额度受限，请稍后再试"),
)


def fatal_reason(exc: BaseException) -> str | None:
    """
    判断异常是否属于「配置类」问题。

    返回中文原因说明；返回 None 表示是 SQL 本身写错了，可以重试修复。
    """
    text = f"{type(exc).__name__}: {exc}".lower()
    for pattern, reason in _FATAL_PATTERNS:
        if pattern in text:
            return reason
    return None


def call_llm(prompt: str) -> str:
    """
    调用大模型生成 SQL。

    两家都是 OpenAI 兼容协议，只是 api_key / base_url / model 不同。
    """
    api_key, base_url, model = resolve_provider()

    if not api_key:
        raise BadRequestError(
            f"未配置 {PROVIDER_LABEL.get(NL2SQL_PROVIDER, NL2SQL_PROVIDER)} 的 API Key，"
            "无法使用 NL2SQL。请在 backend/.env 里填写对应的 Key。"
        )

    if not base_url:
        raise BadRequestError(
            "NL2SQL_PROVIDER=custom 时必须同时填写 NL2SQL_BASE_URL（OpenAI 兼容地址）。"
        )

    # 延迟导入：没装 openai 时，其他接口仍能正常启动
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=NL2SQL_TIMEOUT,
    )
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return (response.choices[0].message.content or "").strip()


def clean_sql(raw: str) -> str:
    """
    清洗模型输出：
    - 去掉 ```sql 代码块；
    - 去掉 “SQL:” 前缀；
    - 只保留第一条语句。
    """
    text = (raw or "").strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:sql)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    text = re.sub(r"^(SQL|sql)\s*[:：]\s*", "", text)

    if ";" in text:
        text = text.split(";")[0].strip()

    return text.strip()


def validate_sql(sql: str, allowed_tables: set[str]) -> None:
    """
    安全校验。

    这是“防删库”的核心之一：
    - 必须以 SELECT 开头；
    - 不允许分号（多语句）；
    - 不允许注释；
    - 不允许危险关键字；
    - FROM / JOIN 后面的表必须在白名单里。
    """
    statement = (sql or "").strip().rstrip(";").strip()

    if not statement:
        raise ValueError("SQL 为空")

    if not re.match(r"(?is)^select\b", statement):
        raise ValueError("只允许执行 SELECT 语句")

    if ";" in statement:
        raise ValueError("不允许多条 SQL 语句")

    if "--" in statement or "/*" in statement:
        raise ValueError("不允许 SQL 注释")

    lowered = statement.lower()

    for keyword in DANGEROUS_KEYWORDS:
        if re.search(rf"\b{keyword}\b", lowered):
            raise ValueError(f"SQL 包含危险操作：{keyword}")

    # 表名可能被加引号（FROM "sys_user" / FROM `sys_user` / FROM [sys_user]），
    # 正则要允许这层包装，否则引号写法会绕过白名单检查。
    tables = re.findall(
        r"\b(?:from|join)\s+[`\"'\[]?([a-zA-Z_][a-zA-Z0-9_]*)[`\"'\]]?",
        lowered,
    )
    for table in tables:
        if table not in allowed_tables:
            raise ValueError(f"表 {table} 不在允许查询的白名单里")


def query(payload: NL2SQLRequest) -> dict:
    """
    自然语言查询主流程。

    返回：
    {
      "sql": 最终 SQL,
      "columns": 字段名,
      "rows": 行数据,
      "message": 提示,
      "attempts": 尝试次数
    }

    失败时抛 DomainError（而不是返回空结果）：
    这样 Dify 的工具节点会走「失败分支」，前端也能显示真正的原因，
    不会让人误以为「查询成功但一条数据都没有」。
    """
    api_key, _, _ = resolve_provider()
    if not api_key:
        raise BadRequestError(
            f"未配置 {PROVIDER_LABEL.get(NL2SQL_PROVIDER, NL2SQL_PROVIDER)} 的 API Key，"
            "无法使用 NL2SQL。请在 backend/.env 里填写对应的 Key。"
        )

    # 前置拦截：用户问了数据库根本没有记录的字段（如性别/年龄），
    # 直接如实说明，不调模型、不生成 SQL——从源头杜绝"把'女'当姓名去查"这类幻觉。
    unsupported = detect_unsupported_field(question := payload.question)
    if unsupported:
        return {
            "sql": "",
            "columns": [],
            "rows": [],
            "message": unsupported,
            "attempts": 0,
            "source": "unsupported",
        }

    schema = repository.get_schema()
    schema_text = schema_to_text(schema)
    allowed_tables = set(schema.keys())

    prompt = build_prompt(question, schema_text)

    # 总时间预算：超过就不再重试，避免 Dify 工具先超时、后端还在空转
    deadline = time.monotonic() + NL2SQL_TIME_BUDGET

    def try_fallback(reason: str) -> dict | None:
        """
        模型用不了时，改用预置查询兜底。

        返回 None 表示没匹配到预置问题，由调用方继续报错。
        降级结果同样要走 validate_sql，保证规则表里也混不进危险 SQL。
        """
        if not NL2SQL_FALLBACK:
            return None
        hit = fallback_sql(question)
        if not hit:
            return None
        sql, note = hit
        try:
            validate_sql(sql, allowed_tables)
            columns, rows = repository.execute_select(sql)
        except Exception:
            return None
        return {
            "sql": sql,
            "columns": columns,
            "rows": rows,
            "message": (
                f"模型不可用（{reason}），已启用演示降级查询「{note}」，"
                f"共 {len(rows)} 行。这是预置 SQL，不是模型生成的。"
            ),
            "attempts": 1,
            "source": "fallback",
        }

    last_sql = ""
    last_error = ""
    attempts = 0

    for attempt in range(1, 4):
        attempts = attempt
        try:
            raw = call_llm(prompt)
            sql = clean_sql(raw)
            last_sql = sql

            validate_sql(sql, allowed_tables)
            columns, rows = repository.execute_select(sql)

            return {
                "sql": sql,
                "columns": columns,
                "rows": rows,
                "message": f"查询成功，共 {len(rows)} 行",
                "attempts": attempt,
                "source": "llm",
            }
        except DomainError:
            # 配置类错误：直接往上抛，不重试
            raise
        except Exception as exc:
            # Key / 额度 / 网络问题：换 SQL 也救不回来，先看能不能降级
            reason = fatal_reason(exc)
            if reason:
                fallback = try_fallback(reason)
                if fallback:
                    return fallback
                raise DomainError(
                    f"NL2SQL 暂时不可用：{reason}",
                    status_code=503,
                    code="llm_unavailable",
                ) from exc

            # 真正的 SQL 错误：带着报错让模型改一版再试
            last_error = str(exc)
            last_sql = last_sql or ""
            if attempt < 3 and time.monotonic() < deadline:
                prompt = fix_prompt(question, last_sql, last_error, schema_text)

    fallback = try_fallback("模型生成的 SQL 无法执行")
    if fallback:
        return fallback

    raise BadRequestError(
        f"没能生成可执行的 SQL（尝试 {attempts} 次）。最后一次的错误：{last_error}"
        "。可以换个更具体的问法，例如「查一下张三的跟进记录」。"
    )
