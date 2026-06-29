"""Planner / Router — 意图识别 + 任务拆解 + 路由决策

2026-06-04 更新：
- 支持细粒度意图（definition/formula/property/derivation/comparison/application/...）
- 接受本地分类器的 hint，减少 LLM 猜测
- Fast Path：simple intent 跳过本节点的 LLM 调用
"""
from config import get_llm

INTENT_PROMPT = """你是一个考研学习规划师。分析用户意图，只返回 JSON。

## 可用意图类型（细粒度）
- definition: 问定义/概念（什么是XX？）
- formula: 问公式/表达式（XX公式是什么？）
- property: 问性质/定理（XX有什么性质？）
- derivation: 推导/证明（怎么推导XX？证明XX？）
- comparison: 比较/区别（XX和YY的区别？）
- application: 应用/计算题（用XX解这道题/计算XX）
- teach: 系统讲解（给我讲XX）
- summarize: 总结/概括（总结XX）
- quiz: 出题测验（出几道XX的题）
- plan: 学习规划（怎么学XX）
- cross_chapter: 跨章节关联问题
- qa: 通用问答（无法归入以上类别）

## 本地分类器提示（供参考，LLM 可覆盖）
{local_hint}

## 已知章节（target_chapters 必须从这些精确名称中选取，不能自行构造小节标题）
{chapters}

## 用户输入
{user_input}

只返回 JSON（不要其他内容）:
{{"intent": "...", "target_chapters": ["..."], "confidence": 0.9, "sub_tasks": [{{"step": 1, "action": "retrieve", "chapter": "..."}}]}}

注意：target_chapters 必须是"已知章节"列表中的精确名称，不要返回小节标题或自行构造的章节名。
"""


def plan_node(state: dict) -> dict:
    """Planner节点：意图识别 + 任务拆解 + 路由

    如果 state 中已有 _local_intent（Fast Path 未命中但本地有 hint），
    将其传入 LLM prompt 减少猜测。
    """
    import json
    from ingestion.vector_store import get_vector_store

    user_input = state.get("user_input", "")
    if not user_input:
        return {"intent": "qa", "target_chapters": [], "sub_tasks": [], "error": "empty input"}

    vs = get_vector_store()
    chapters = vs.get_chapter_names()

    # 读取本地分类器 hint（如果有）
    local_hint = state.get("_local_intent_hint", "无")

    llm = get_llm()
    prompt = INTENT_PROMPT.format(
        chapters="\n".join(f"- {c}" for c in chapters) if chapters else "（无章节）",
        user_input=user_input,
        local_hint=local_hint,
    )
    result = llm.invoke(prompt).content.strip()

    if result.startswith("```"):
        result = result.split("\n", 1)[-1].rsplit("\n", 1)[0]

    try:
        plan = json.loads(result)
    except json.JSONDecodeError:
        # 降级：如果本地有分类结果，直接用它
        fallback_intent = state.get("_local_intent", "qa")
        plan = {
            "intent": fallback_intent,
            "target_chapters": chapters[:1] if chapters else [],
            "sub_tasks": [],
        }

    intent = plan.get("intent", "qa")
    target_chapters = plan.get("target_chapters", [])
    sub_tasks = plan.get("sub_tasks", [])

    # 如果 planner 没指定章节，用向量检索找
    if not target_chapters and chapters:
        target_chapters = _find_relevant_chapters(user_input, chapters, vs)

    # 为 teach/summarize 意图构建分步任务
    if intent in ("teach", "summarize") and not sub_tasks and target_chapters:
        ch = target_chapters[0]
        sub_tasks = [
            {"step": 1, "action": "retrieve", "description": f"获取{ch}内容", "chapter": ch},
            {"step": 2, "action": "extract_keypoints", "description": "提炼重点概念", "chapter": ch},
            {"step": 3, "action": "teach", "description": "生成讲解", "chapter": ch},
            {"step": 4, "action": "summarize", "description": "生成总结", "chapter": ch},
        ]
        if intent == "teach":
            sub_tasks.append({"step": 5, "action": "quiz", "description": "生成练习题", "chapter": ch})

    return {
        "intent": intent,
        "target_chapters": target_chapters,
        "sub_tasks": sub_tasks,
        "route_decision": intent,
    }


def _find_relevant_chapters(question: str, chapters: list[str], vs) -> list[str]:
    """用向量检索找相关章节"""
    all_results = vs.search_all(question, k=1)
    return list(all_results.keys())[:3]
