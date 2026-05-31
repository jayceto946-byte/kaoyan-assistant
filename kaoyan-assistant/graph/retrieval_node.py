"""检索节点 — 章节检索 + 概念检索 + 历史记忆 三合一"""
from config import get_llm
from ingestion.vector_store import ChapterVectorStore
from knowledge.knowledge_graph import KnowledgeGraph


def retrieve_node(state: dict) -> dict:
    """检索节点：合并三个检索源"""
    target_chapters = state.get("target_chapters", [])
    user_input = state.get("user_input", "")
    book_name = state.get("book_name", "default")

    vs = ChapterVectorStore()
    chapter_contents = {}
    concept_results = []

    # 1. 章节检索
    for ch in target_chapters:
        docs = vs.search_chapter(ch, user_input, k=6)
        if docs:
            chapter_contents[ch] = [d.page_content for d in docs]
    if not chapter_contents:
        all_results = vs.search_all(user_input, k=2)
        for ch_name, docs in all_results.items():
            chapter_contents[ch_name] = [d.page_content for d in docs]

    # 2. 概念检索 — 搜索所有章节
    all_docs = vs.search_all(user_input, k=3)
    for ch_name, docs in all_docs.items():
        for d in docs:
            concept_results.append({
                "chapter": ch_name,
                "content": d.page_content[:300],
                "chunk_id": d.metadata.get("chunk_id", ""),
            })

    # 3. 知识图谱关联
    kg = KnowledgeGraph(book_name)
    kg_path = []
    if target_chapters:
        kg_path = kg.find_path(target_chapters[0], user_input)

    # 4. 历史记忆 (从 progress 读取)
    history_results = _load_history(book_name, target_chapters)

    return {
        "chapter_contents": chapter_contents,
        "concept_results": concept_results,
        "history_results": history_results,
        "knowledge_graph_path": kg_path,
    }


def _load_history(book_name: str, chapters: list[str]) -> list[dict]:
    """从学习记录加载历史上下文"""
    import json
    from pathlib import Path
    from config import PROGRESS_PATH

    results = []
    progress_dir = Path(PROGRESS_PATH) / book_name

    # 错题记录
    weakness_file = progress_dir / "weakness.json"
    if weakness_file.exists():
        with open(weakness_file, "r", encoding="utf-8") as f:
            weak = json.load(f)
            for w in weak[-10:]:
                results.append({"type": "weakness", "chapter": w})

    # 答题历史
    quiz_file = progress_dir / "quiz_history.json"
    if quiz_file.exists():
        with open(quiz_file, "r", encoding="utf-8") as f:
            quiz_history = json.load(f)
            for q in quiz_history[-10:]:
                results.append({
                    "type": "quiz",
                    "chapter": q.get("chapter", ""),
                    "correct": q.get("correct", False),
                    "question": q.get("question", "")[:80],
                })

    return results
