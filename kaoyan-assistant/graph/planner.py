"""Planner / Router — 意图识别 + 任务拆解 + 路由决策"""
from config import get_llm

INTENT_PROMPT = """你是一个考研学习规划师。分析用户意图，只返回 JSON。

## 可用意图类型
- qa: 简单问答
- teach: 知识点讲解
- summarize: 总结/概括
- quiz: 出题测验
- plan: 学习规划
- cross_chapter: 跨章节关联问题

## 已知章节
{chapters}

## 用户输入
{user_input}

只返回 JSON（不要其他内容）:
{{"intent": "...", "target_chapters": ["..."], "confidence": 0.9, "sub_tasks": [{{"step": 1, "action": "retrieve", "chapter": "..."}}]}}
"""


def plan_node(state: dict) -> dict:
    """Planner节点：意图识别 + 任务拆解 + 路由"""
    import json
    from ingestion.vector_store import ChapterVectorStore

    user_input = state.get("user_input", "")
    if not user_input:
        return {"intent": "qa", "target_chapters": [], "sub_tasks": [], "error": "empty input"}

    vs = ChapterVectorStore()
    chapters = vs.get_chapter_names()

    llm = get_llm(temperature=0)
    prompt = INTENT_PROMPT.format(
        chapters="\n".join(f"- {c}" for c in chapters) if chapters else "（无章节）",
        user_input=user_input,
    )
    result = llm.invoke(prompt).content.strip()

    if result.startswith("```"):
        result = result.split("\n", 1)[-1].rsplit("\n", 1)[0]

    try:
        plan = json.loads(result)
    except json.JSONDecodeError:
        # 降级：简单路由
        plan = {"intent": "qa", "target_chapters": chapters[:1] if chapters else [], "sub_tasks": []}

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
