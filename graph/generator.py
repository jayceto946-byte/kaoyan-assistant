"""综合生成 Agent — 信息整合 + 推理生成 + 格式化输出"""
from config import get_llm
from utils.latex_sanitizer import sanitize_latex
from utils.thinking_filter import strip_thinking

_EXAMPLE_CHECK_PROMPT = """
【例题完整性自检】
在引用教材例题前，请先检查检索到的内容中是否有以"例X.X"或"例X"开头的完整题干。
- 如果有完整题干：完整复述题干，然后逐步拆解解题过程。
- 如果只有解题步骤但没有完整题干，或完全没有例题相关内容：
  允许你基于检索到的概念定义和公式，自行构造一道等效例题来辅助讲解。
  自行构造的例题必须满足以下条件：
  ① 涉及的核心概念与检索内容一致，不得引入未检索到的概念；
  ② 难度和计算复杂度与教材例题相当，不得过于简单或过于复杂；
  ③ 使用的公式、符号体系与教材一致（如教材用 x^(k)，你的例题也用 x^(k)）；
  ④ 在例题开头明确标注"[补充例题]"，并在题后简要说明构造理由。
"""

GENERATE_PROMPT = """请基于以下信息回答用户问题。直接开始，不要寒暄。

## 用户意图：{intent}
## 用户问题：{user_input}

## 教材内容
{chapter_content}

## 概念检索
{concept_results}

## 学习者历史
{history_results}

## 知识关联
{kg_path}

## 章节教学产出
{teaching_content}

## 要求
1. 概念定义请使用教材原文表述，如"某某概念是指……"、"某某概念是……"
2. 遇到用户可能第一次接触、或本身比较抽象陌生的概念时，请在正式定义后补一个简短的“直观例子”或“生活化类比”，用日常场景说明它具体怎么体现；例子只用于帮助理解，不能替代教材定义、适用条件、公式推导或例题解法。
3. 讲解结构要保留“以题讲知识点”的主线：概念只列必要项，每个核心概念尽量落回题目、公式、步骤或易错点，不要把回答写成概念清单。
4. {example_check}
5. 公式使用LaTeX：行内$...$，块级$$...$$；所有 $ / $$ 必须成对闭合，不能把中文文字或标点包在数学模式内
6. {output_instruction}
"""

GENERAL_QA_PROMPT = """You are a postgraduate-study assistant answering in Chinese without textbook RAG context.
Current subject: {subject}
User intent: {intent}
User question: {user_input}

Recent study memory:
{history_results}

Requirements:
1. Answer directly in Chinese and do not mention that there is no textbook unless the user asks about sources.
2. For unfamiliar or abstract concepts, give the formal explanation first, then add one short life-like example that makes the idea concrete.
3. Keep a problem-led structure: use definitions only as needed, then connect the concept back to the question, formulas, steps, or common mistakes.
4. For calculation or proof questions, solve step by step and explain why each step is used.
5. Use LaTeX for formulas: inline $...$ and display $$...$$. Every delimiter must be balanced.
6. {output_instruction}
"""

def _has_example_marker(text: str) -> bool:
    """检测文本中是否包含教材例题标记（如'例4-2'、'例3'等）。"""
    import re
    return bool(re.search(r'例\s*\d+([\-\.]\d+)?', text))


def _build_generate_prompt(state: dict) -> str:
    """根据 state 构建生成 prompt（供流式 runner 复用）。"""
    intent = state.get("intent", "qa")
    user_input = state.get("user_input", "")

    chapter_contents = state.get("chapter_contents", {})
    chapter_text = ""
    for ch, docs in list(chapter_contents.items())[:2]:
        # 提高截断上限并保留更多 doc，减少例题题干被截断的概率
        chapter_text += f"\n## {ch}\n" + "\n---\n".join(d[:1500] for d in docs[:3])

    concept_results = state.get("concept_results", [])
    concept_text = "\n".join(
        f"- [{c.get('chapter', '')}] {c.get('content', '')[:200]}"
        for c in concept_results[:3]
    )

    history_results = state.get("history_results", [])
    history_text = "\n".join(
        f"- [{h.get('type', '')}] {h.get('chapter', '')}: {h.get('question', '')}"
        for h in history_results[:3]
    )

    kg_path = state.get("knowledge_graph_path", [])
    kg_text = " → ".join(kg_path) if kg_path else "无"

    teaching_content = state.get("teaching_content", "")

    output_instruction = {
        "qa": "简洁准确地回答，需要解释的地方充分展开。",
        "definition": "先给出概念定义（使用教材原文表述），必要时用一个生活化直观例子垫一下，然后附一道例题并逐步拆解。",
        "formula": "先给出公式和含义，然后附一道运用该公式的例题并逐步拆解。",
        "property": "列出关键性质/定理，附一道相关例题并逐步拆解。",
        "derivation": "给出推导/证明过程，附一道验证题并逐步拆解。",
        "comparison": "对比异同，附一道例题在解题中展示实际区别。",
        "application": "给出完整解题步骤，逐步拆解，标注易错点。",
        "teach": "系统讲解本章，以例题为主线逐步展开；遇到陌生概念先用简短生活化例子帮助理解，再回到题目和公式。",
        "summarize": "生成结构化总结：核心概念、公式速查、知识框架；抽象新概念可附一句生活化直观例子，但不要变成概念罗列。",
        "quiz": "直接输出题目列表。",
        "plan": "给出学习计划，每天明确任务。",
        "cross_chapter": "说明章节间的知识关联和递进关系。",
    }.get(intent, "清晰回答用户问题。")

    if not state.get("use_textbook_context", True):
        return GENERAL_QA_PROMPT.format(
            subject=state.get("subject") or "未指定",
            intent=intent,
            user_input=user_input,
            history_results=history_text or "(none)",
            output_instruction=output_instruction,
        )
    # 检测检索内容中是否包含例题标记
    has_example_marker = _has_example_marker(chapter_text)
    _FALLBACK_EXAMPLE_PROMPT = (
        "涉及例题时请基于检索到的完整题干逐步拆解。"
        "若检索到的例题题干不完整，允许你基于检索到的概念定义和公式自行构造一道等效例题，"
        "但必须满足：①核心概念一致；②难度相当；③公式符号与教材一致；④标注[补充例题]。"
    )
    example_check = _EXAMPLE_CHECK_PROMPT if has_example_marker else _FALLBACK_EXAMPLE_PROMPT

    return GENERATE_PROMPT.format(
        intent=intent,
        user_input=user_input,
        chapter_content=chapter_text or "（未找到相关章节）",
        concept_results=concept_text or "（无）",
        history_results=history_text or "（无）",
        kg_path=kg_text,
        teaching_content=teaching_content or "（无）",
        example_check=example_check,
        output_instruction=output_instruction,
    )


def _format_quiz_appendix(state: dict) -> str:
    """如果 intent 是 quiz 且已生成题目，返回附加 HTML。"""
    intent = state.get("intent", "")
    quiz_questions = state.get("quiz_questions", [])
    if intent != "quiz" or not quiz_questions:
        return ""
    quiz_text = "\n\n## 练习题\n"
    for i, q in enumerate(quiz_questions[:5], 1):
        quiz_text += f"\n**{i}. {q.get('question', '')}**\n"
        if q.get("options"):
            for opt in q["options"]:
                quiz_text += f"  {opt}\n"
        quiz_text += f"\n<details><summary>答案</summary>{q.get('answer', '')}</details>\n"
    return quiz_text


def generate_node(state: dict) -> dict:
    """生成节点：整合所有检索和教学结果，生成最终输出"""
    intent = state.get("intent", "qa")
    output_type = state.get("output_type", "text")
    teaching_content = state.get("teaching_content", "")

    # 优化：teach/summarize 意图直接复用 chapter_subgraph 已生成的内容，跳过冗余 LLM
    if intent in ("teach", "summarize") and teaching_content:
        final = teaching_content
        chapter_summary = state.get("chapter_summary", "")
        if chapter_summary and intent == "summarize":
            final = chapter_summary
        elif chapter_summary:
            final += f"\n\n---\n\n## 章节总结\n{chapter_summary}"
    else:
        llm = get_llm()
        prompt = _build_generate_prompt(state)
        final = llm.invoke(prompt).content

    final += _format_quiz_appendix(state)

    # 过滤 DeepSeek thinking 内容，只保留正式回答
    final = strip_thinking(final)
    # 修复 LLM 可能产生的未闭合 LaTeX 定界符，避免前端 KaTeX 报红
    final = sanitize_latex(final)

    return {
        "final_output": final,
        "output_type": output_type,
    }
