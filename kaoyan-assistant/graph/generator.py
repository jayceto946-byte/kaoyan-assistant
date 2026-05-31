"""综合生成 Agent — 信息整合 + 推理生成 + 格式化输出"""
from config import get_llm

GENERATE_PROMPT = """你是一个考研辅导专家。综合以下信息，生成最终回答。

## 用户意图：{intent}
## 用户问题：{user_input}

## 章节内容
{chapter_content}

## 概念检索
{concept_results}

## 学习者历史
{history_results}

## 知识关联
{kg_path}

## 章节教学产出
{teaching_content}

## 回答要求
1. 针对用户意图给出精准回答
2. 引用教材内容时标注来源
3. 公式使用 LaTeX（$...$ 或 $$...$$）
4. 如有知识关联，说明前后依赖关系
5. {output_instruction}
"""


def generate_node(state: dict) -> dict:
    """生成节点：整合所有检索和教学结果，生成最终输出"""
    intent = state.get("intent", "qa")
    user_input = state.get("user_input", "")

    # 整合章节内容
    chapter_contents = state.get("chapter_contents", {})
    chapter_text = ""
    for ch, docs in chapter_contents.items():
        chapter_text += f"\n## {ch}\n" + "\n---\n".join(d[:500] for d in docs[:4])

    # 概念检索
    concept_results = state.get("concept_results", [])
    concept_text = "\n".join(
        f"- [{c.get('chapter', '')}] {c.get('content', '')[:200]}"
        for c in concept_results[:5]
    )

    # 历史
    history_results = state.get("history_results", [])
    history_text = "\n".join(
        f"- [{h.get('type', '')}] {h.get('chapter', '')}: {h.get('question', '')}"
        for h in history_results[:5]
    )

    # 知识图谱
    kg_path = state.get("knowledge_graph_path", [])
    kg_text = " → ".join(kg_path) if kg_path else "无"

    # 教学产出
    teaching_content = state.get("teaching_content", "")
    quiz_questions = state.get("quiz_questions", [])

    # 输出指令
    output_type = state.get("output_type", "text")
    output_instruction = {
        "qa": "简洁准确地回答问题，附带必要的解释。",
        "teach": "系统讲解，从基础到深入，配合例题和关键公式。",
        "summarize": "生成结构化总结，包含核心概念、公式速查、知识框架。",
        "quiz": "直接输出题目列表。",
        "plan": "以列表形式给出学习计划，每天明确任务。",
        "cross_chapter": "说明章节间的知识关联和递进关系。",
    }.get(intent, "清晰回答用户问题。")

    llm = get_llm(temperature=0.3)
    prompt = GENERATE_PROMPT.format(
        intent=intent,
        user_input=user_input,
        chapter_content=chapter_text or "（未找到相关章节）",
        concept_results=concept_text or "（无）",
        history_results=history_text or "（无）",
        kg_path=kg_text,
        teaching_content=teaching_content or "（无）",
        output_instruction=output_instruction,
    )

    answer = llm.invoke(prompt).content
    final = answer

    # 如果是 quiz 意图，附加题目列表
    if intent == "quiz" and quiz_questions:
        quiz_text = "\n\n## 📝 练习题\n"
        for i, q in enumerate(quiz_questions[:5], 1):
            quiz_text += f"\n**{i}. {q.get('question', '')}**\n"
            if q.get("options"):
                for opt in q["options"]:
                    quiz_text += f"  {opt}\n"
            quiz_text += f"\n<details><summary>答案</summary>{q.get('answer', '')}</details>\n"
        final = answer + quiz_text

    return {
        "final_output": final,
        "output_type": output_type,
    }
