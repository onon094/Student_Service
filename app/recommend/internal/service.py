"""
画像研判与推荐模块的 Service（业务层）。

核心思想：
- 大模型负责“抽取画像”和“组织话术”；
- 规则引擎负责“做推荐决定”，保证可解释、可复现、不编造。

推荐规则（来自需求文档）：
- 初中 -> 2+2 / 2+2+1
- 高中 / 中职 -> 0.5/1+2 / 0.5/1+2+1
- 中职且满 17 岁 -> 6+6 / 9+6
- 专科 -> 一年制专升本
- 本科 -> 一年制本升硕
- 德国双元制 -> 18-35 岁、高中及以上、德语 B1、动手能力强

匹配分规则（基础 70 分起，逐项累加，封顶 100）：
- 意向匹配：就业 +8 / 移民 +8 / 升学 +6
- 国家意向匹配（新增）：用户想去哪，项目就在哪 +6
- 德国项目专项：德语基础 +5、动手能力强 +5
- 预算只解析记录、不参与打分：course_project 表无费用字段，
  与其编一个费用数字，不如如实说明该维度缺数据（对应"不编造"原则）。
"""

from __future__ import annotations

import re

from app.catalog import api as catalog_api
from app.recommend.schemas import MatchItem, RecommendRequest

# 学历关键词，按优先级从高到低匹配
EDUCATION_KEYWORDS = [
    ("硕士", ["硕士", "研究生"]),
    ("本科", ["本科", "学士"]),
    ("专科", ["专科", "大专", "高职"]),
    ("中职技校", ["中职", "中专", "技校", "职高"]),
    ("高中", ["高中"]),
    ("初中", ["初中"]),
]

# 意向关键词
EMPLOYMENT_WORDS = ["就业", "工作", "找工作", "就业班"]
IMMIGRATION_WORDS = ["移民", "永居", "绿卡"]
STUDY_WORDS = ["升学", "本科", "硕士", "留学", "深造", "学历", "读书"]

# 目标国家关键词：用于把用户"想去哪"和项目名里的国家字样对上
COUNTRY_WORDS = {
    "德国": ["德国", "德意志"],
    "新加坡": ["新加坡", "狮城", "sg"],
}


def normalize_education(text: str) -> str:
    """
    学历归一化。

    关键：要区分“当前学历”和“目标学历”。
    例：
    - “高中刚毕业，想拿本科学历” -> 高中（不是本科）
    - “本科毕业，想读硕士”       -> 本科
    - “大专毕业”                 -> 专科
    - “中专”                     -> 中职技校
    """
    content = text or ""

    # 1. 先看“当前学历”的强语境：X 毕业 / X 在读 / X 刚毕业
    strong_patterns = [
        ("初中", r"(初中|初二|初三)[^，。；\n]{0,6}(毕业|在读|刚毕业)"),
        ("高中", r"(高中|高二|高三)[^，。；\n]{0,6}(毕业|在读|刚毕业)"),
        ("中职技校", r"(中职|中专|技校|职高)[^，。；\n]{0,6}(毕业|在读|刚毕业)"),
        ("专科", r"(专科|大专|高职)[^，。；\n]{0,6}(毕业|在读|刚毕业)"),
        ("本科", r"本科[^，。；\n]{0,6}(毕业|在读|刚毕业)"),
        ("硕士", r"硕士[^，。；\n]{0,6}(毕业|在读|刚毕业)"),
    ]
    for bucket, pattern in strong_patterns:
        if re.search(pattern, content):
            return bucket

    # 2. 去掉“目标学历”短语，避免把“想拿本科学历”误判成当前本科
    cleaned = re.sub(
        r"(拿|读|升|考|想读|想拿|目标|申请)[^，。；\n]{0,4}(本科|硕士|专科|大专)",
        "",
        content,
    )

    # 3. 最后再看普通关键词
    for bucket, words in EDUCATION_KEYWORDS:
        if any(word in cleaned for word in words):
            return bucket
    return ""


def normalize_intent(text: str) -> str:
    """
    意向归一化：就业 / 移民 / 升学，默认升学。
    """
    content = text or ""
    if any(word in content for word in IMMIGRATION_WORDS):
        return "移民"
    if any(word in content for word in EMPLOYMENT_WORDS):
        return "就业"
    if any(word in content for word in STUDY_WORDS):
        return "升学"
    return "升学"


def normalize_country(text: str) -> str:
    """目标国家归一化：从用户描述里找"德国/新加坡"，找不到返回空串。"""
    content = (text or "").lower()
    for country, words in COUNTRY_WORDS.items():
        if any(word.lower() in content for word in words):
            return country
    return ""


def extract_budget(text: str) -> int | None:
    """
    从描述里抽预算数字（单位：万元），例如"预算20万" -> 20。
    注意：只做识别展示，不参与打分（项目表无费用字段，避免编造费用匹配）。
    """
    matched = re.search(r"(\d+)\s*万", text or "")
    return int(matched.group(1)) if matched else None


def extract_profile(raw_text: str, structured: dict | None = None) -> dict:
    """
    抽取画像字段。

    优先用 structured（大模型已经抽好的），缺失字段再用正则兜底。
    """
    profile = {
        "age": None,
        "education": "",
        # 先留空，等结构化字段或关键词判断后再给默认值，
        # 否则默认“升学”会让后面的“就业 / 移民”判断永远不执行。
        "intent": "",
        "language": "",
        "hands_on": False,
        # 新增两项：目标国家（参与加分）、预算万元（仅展示，不加分）
        "country": "",
        "budget": None,
        "raw_text": raw_text,
    }

    # 1. 先吃结构化字段
    if structured:
        if structured.get("age") not in (None, ""):
            try:
                profile["age"] = int(structured["age"])
            except (TypeError, ValueError):
                pass
        if structured.get("education"):
            profile["education"] = str(structured["education"])
        if structured.get("intent"):
            profile["intent"] = str(structured["intent"])
        if structured.get("language"):
            profile["language"] = str(structured["language"])
        if structured.get("hands_on") is not None:
            profile["hands_on"] = bool(structured["hands_on"])
        if structured.get("country"):
            profile["country"] = str(structured["country"])
        if structured.get("budget") not in (None, ""):
            try:
                profile["budget"] = int(structured["budget"])
            except (TypeError, ValueError):
                pass

    # 2. 正则 / 关键词兜底
    if profile["age"] is None:
        matched = re.search(r"(\d{1,2})\s*岁", raw_text)
        if matched:
            profile["age"] = int(matched.group(1))

    if not profile["education"]:
        profile["education"] = normalize_education(raw_text)

    if profile["intent"] not in ("就业", "移民", "升学"):
        # 没传、或 structured 传了不规范的值，都用文本兜底
        profile["intent"] = normalize_intent(raw_text)

    if not profile["language"]:
        if "德语" in raw_text or "B1" in raw_text.upper():
            profile["language"] = "德语"
        elif "英语" in raw_text or "雅思" in raw_text or "托福" in raw_text:
            profile["language"] = "英语"

    if "动手" in raw_text:
        profile["hands_on"] = True

    if not profile["country"]:
        profile["country"] = normalize_country(raw_text)
    if profile["budget"] is None:
        profile["budget"] = extract_budget(raw_text)

    return profile


def _match_project(project: dict, profile: dict) -> bool:
    """判断一个项目是否进入候选池。"""
    name = project.get("project_name") or ""
    education = profile.get("education")
    age = profile.get("age")

    # 德国双元制：18-35 岁 + 高中及以上
    if "德国" in name:
        if education not in ("高中", "中职技校", "专科", "本科"):
            return False
        if age is None:
            return False
        return 18 <= age <= 35

    # 学历提升
    if "专升本" in name:
        return education == "专科"
    if "本升硕" in name:
        return education == "本科"

    # 新加坡国际本科 / 本硕
    if name.startswith("2+2"):
        return education == "初中"
    if name.startswith("0.5/1+2"):
        return education in ("高中", "中职技校")

    # 就业班：中职技校 + 满 17 岁
    if "6+6" in name or "9+6" in name:
        return education == "中职技校" and age is not None and age >= 17

    return False


def _score_detail(project: dict, profile: dict) -> tuple[int, list[str]]:
    """
    计算匹配度，返回 (分数, 加分明细)。
    基础 70 分起，逐项累加，封顶 100。
    关键：分数和理由用同一份明细生成，绝不出现"说加了3分、实际算的不同"。
    """
    score = 70
    details: list[str] = []
    name = project.get("project_name") or ""
    category = project.get("category") or ""
    intent = profile.get("intent")

    # 1) 意向匹配：就业/移民给 8 分、升学给 6 分，拉开与非意向项目的差距
    if intent == "就业" and category in ("就业班", "德国项目"):
        score += 8
        details.append("就业意向匹配 +8")
    elif intent == "移民" and category == "德国项目":
        score += 8
        details.append("移民意向匹配 +8")
    elif intent == "升学" and category in ("国际本科", "本硕连读", "学历提升"):
        score += 6
        details.append("升学意向匹配 +6")

    # 2) 目标国家匹配（新增）：用户想去哪，项目就在哪。项目名含国家字样
    country = profile.get("country")
    if country and country in name:
        score += 6
        details.append(f"目标国家 {country} 匹配 +6")

    # 3) 德国专项：德语 B1、动手能力强（德国双元制的明确门槛）
    if "德国" in name:
        if profile.get("language") == "德语":
            score += 5
            details.append("有德语基础 +5")
        if profile.get("hands_on"):
            score += 5
            details.append("动手能力强 +5")

    return min(score, 100), details


def _score_project(project: dict, profile: dict) -> int:
    """取分数；保留此函数签名，避免影响调用方。"""
    return _score_detail(project, profile)[0]


def _build_reason(project: dict, profile: dict, score: int) -> str:
    """生成可解释的推荐理由：每条加分都对应一处分数变化。"""
    _, details = _score_detail(project, profile)
    reasons = [f"学历={profile.get('education') or '未识别'}，进入该项目池（基础70）"]
    reasons.extend(details)

    # 预算如实说明：识别到了也只展示，不假装做了费用匹配
    if profile.get("budget"):
        reasons.append(f"预算{profile['budget']}万（项目表无费用字段，暂不参与评分）")

    return "；".join(reasons) + f"；匹配度 {score} 分"


def recommend(payload: RecommendRequest) -> dict:
    """
    推荐主流程：

    1. 抽取画像；
    2. 读课程 / 项目（通过 catalog.api，不直接查表）；
    3. 规则匹配 + 打分 + 排序；
    4. 返回最优推荐、理由、匹配度和中文摘要。
    """
    profile = extract_profile(payload.raw_text, payload.structured)
    projects = catalog_api.list_projects()

    matches: list[dict] = []
    for project in projects:
        if not _match_project(project, profile):
            continue

        score = _score_project(project, profile)
        matches.append(
            {
                "project_id": project["id"],
                "project_name": project["project_name"],
                "category": project.get("category"),
                "reason": _build_reason(project, profile, score),
                "score": score,
                "_sort": project["id"],
            }
        )

    # 分数从高到低；同分按项目 id 稳定排序
    matches.sort(key=lambda item: (-item["score"], item["_sort"]))
    for item in matches:
        item.pop("_sort", None)

    best = matches[0] if matches else None

    if best:
        name = payload.name or "该同学"
        summary = (
            f"{name}（{profile.get('education') or '学历未识别'}）"
            f"推荐【{best['project_name']}】，匹配度 {best['score']} 分。"
        )
    else:
        summary = "根据当前画像没有匹配到合适项目，建议补充年龄、学历、意向后再试。"

    return {
        "profile": profile,
        "matches": matches,
        "best_match": best,
        "summary": summary,
    }
