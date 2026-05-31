"""参数化章节教学 Subgraph — 一个通用图，按 chapter_name 注入不同内容

Pipeline: 获取内容 → 提炼重点 → 生成讲解 → 例题解析 → 出题巩固
"""
import json
from config import get_llm
from ingestion.vector_store import ChapterVectorStore
from knowledge.summary_store import SummaryStore

EXTRACT_KEYPOINTS_PROMPT = """基于以下章节内容，提取考研重点：

## 章节内容
{content}

输出 JSON（不要其他）：
{{
  "key_concepts": ["概念1", "概念2"],
  "key_formulas": ["公式1", "公式2"],
  "key_theorems": ["定理1"],
  "common_mistakes": ["易错点1"],
  "exam_frequency": "高/中/低"
}}
"""

TEACH_PROMPT = """你是一位考研辅导名师。请基于以下内容讲解这一章。

## 章节：{chapter}
## 内容
{content}

## 重点概念
{key_points}

## 讲解要求
1. 从基础概念开始，逐步深入
2. 用通俗语言解释，配合公式（LaTeX）
3. 强调考研高频考点和易错点
4. 给出典型例题的解题思路
5. 总结本章知识框架
"""

SUMMARIZE_PROMPT = """请对以下章节生成精简总结：

## 章节：{chapter}
## 讲解内容
{teaching}

## 要求
1. 1000字以内
2. 包含核心概念、公式速查、知识脉络
3. 标注★★★重点
"""


def chapter_subgraph_run(state: dict) -> dict:
    """参数化章节教学流水线

    根据 state.target_chapters[0] 加载对应章节内容，执行教学流水线。
    所有章节共用同一个 subgraph，通过 chapter_name 参数化。
    """
    target = state.get("target_chapters", [])
    if not target:
        return {"teaching_content": "未指定章节", "error": "no_chapter"}

    chapter = target[0]
    user_input = state.get("user_input", "")
    intent = state.get("intent", "teach")
    book_name = state.get("book_name", "default")

    vs = ChapterVectorStore()
    llm = get_llm(temperature=0.3)

    # Step 1: 获取内容
    docs = vs.search_chapter(chapter, user_input + " 重点 概念 定义", k=8)
    if not docs:
        docs = vs.search_chapter(chapter, "全部内容", k=10)
    content = "\n\n".join(d.page_content for d in docs) if docs else "（无内容）"

    # Step 2: 尝试从缓存获取摘要
    ss = SummaryStore(book_name)
    cached = ss.get(chapter)

    # Step 3: 提取重点
    key_points_str = ""
    if cached:
        key_points_str = "\n".join(cached.get("key_points", []))
    else:
        resp = llm.invoke(EXTRACT_KEYPOINTS_PROMPT.format(content=content[:4000]))
        try:
            kp = json.loads(_clean_json(resp.content))
            key_points_str = "\n".join(kp.get("key_concepts", []))
        except json.JSONDecodeError:
            key_points_str = ""

    # Step 4: 生成讲解
    if intent in ("teach", "summarize"):
        teaching = llm.invoke(TEACH_PROMPT.format(
            chapter=chapter,
            content=content[:6000],
            key_points=key_points_str or "从内容中提取",
        )).content
    else:
        teaching = f"## {chapter}\n\n{content[:3000]}"

    examples = []
    quiz_questions = []

    # Step 5: 出题（如果是 teach 意图）
    if intent == "teach":
        quiz_questions = _generate_quiz(chapter, content, llm)

    # Step 6: 总结
    summary = ""
    if intent in ("teach", "summarize"):
        summary = llm.invoke(SUMMARIZE_PROMPT.format(
            chapter=chapter,
            teaching=teaching[:4000],
        )).content
        # 缓存
        ss.set(chapter, {
            "summary": summary,
            "key_points": key_points_str.split("\n") if key_points_str else [],
            "teaching": teaching[:2000],
        })

    return {
        "teaching_content": teaching,
        "key_points": key_points_str.split("\n") if key_points_str else [],
        "extracted_examples": examples,
        "quiz_questions": quiz_questions,
        "chapter_summary": summary,
    }


def _generate_quiz(chapter: str, content: str, llm) -> list[dict]:
    prompt = f"""基于以下章节内容，生成 3 道选择题和 2 道填空题。

## 章节：{chapter}
## 内容
{content[:4000]}

输出 JSON 数组（不要其他）：
[
  {{"question": "...", "type": "选择题", "options": ["A.","B.","C.","D."], "answer": "A", "explanation": "...", "knowledge_point": "..."}},
  ...
]
"""
    resp = llm.invoke(prompt)
    try:
        return json.loads(_clean_json(resp.content))
    except json.JSONDecodeError:
        return [{"question": "出题失败", "type": "text", "error": True}]


def _clean_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("\n", 1)[0]
    return text
