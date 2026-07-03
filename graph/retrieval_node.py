"""检索节点 — 三层混合检索：KG精确命中 → 向量补充(role优先) → 去重重排"""
from graph.safe_retrieval import get_safe_kg, get_safe_vector_store

# intent → 优先 role 列表（越靠前越优先）
INTENT_ROLE_PRIORITY: dict[str, list[str]] = {
    "definition":   ["definition", "theorem", "property", "example", "derivation"],
    "formula":      ["definition", "property", "derivation", "example"],
    "property":     ["property", "theorem", "definition", "example"],
    "derivation":   ["derivation", "theorem", "proof", "definition"],
    "comparison":   ["definition", "property", "example"],
    "application":  ["example", "algorithm", "exercise", "derivation"],
    "teach":        ["definition", "example", "algorithm", "property", "derivation"],
    "summarize":    ["definition", "property", "theorem", "derivation"],
    "quiz":         ["example", "exercise", "derivation"],
    "plan":         ["definition", "algorithm", "property"],
    "cross_chapter":["definition", "property", "theorem"],
    "qa":           ["definition", "theorem", "property", "example", "derivation"],
}


def retrieve_node(state: dict) -> dict:
    """检索节点：三层混合检索（KG精确 → 向量补充(role优先) → 去重重排）"""
    target_chapters = state.get("target_chapters", [])
    user_input = state.get("user_input", "")
    book_name = state.get("book_name", "default")
    intent = state.get("intent", "qa")

    if not state.get("use_textbook_context", True):
        return {
            "chapter_contents": {},
            "concept_results": [],
            "history_results": [],
            "knowledge_graph_path": [],
            "knowledge_graph_formulas": [],
            "matched_concepts": [],
            "retrieval_status": "ordinary_qa",
            "retrieval_error": "",
        }

    retrieval_errors = []
    if state.get("retrieval_error"):
        retrieval_errors.append(str(state.get("retrieval_error")))

    vs, vector_error = get_safe_vector_store()
    kg, kg_error = get_safe_kg(book_name)
    if vector_error:
        retrieval_errors.append(f"vector_store: {vector_error}")
    if kg_error:
        retrieval_errors.append(f"knowledge_graph: {kg_error}")

    # ═══════════════════════════════════════════════════════════════
    # 第1层：KG 关键词精确命中（最高优先级）
    # ═══════════════════════════════════════════════════════════════
    precise_results, matched_concepts = _kg_precise_retrieval(kg, user_input)

    # ═══════════════════════════════════════════════════════════════
    # 第2层：向量检索（按 intent → role 优先级过滤）
    #   - 有精确命中章节：在该章节内按 role 优先级搜索
    #   - 无精确命中：全库按 role 优先级搜索
    # ═══════════════════════════════════════════════════════════════
    vector_results = _vector_retrieval(
        vs,
        user_input,
        intent=intent,
        book_name=book_name,
        target_chapters=target_chapters,
        precise_chapters=list({r["chapter"] for r in precise_results}),
        k=3,
        top_n=2,
    )

    # ═══════════════════════════════════════════════════════════════
    # 第3层：合并去重 + 重排序
    #   - 精确命中 chunk 排最前（带上下文窗口）
    #   - 向量结果去重后接在后面
    #   - 同一章节最多保留 5 个 chunk，避免 prompt 膨胀
    # ═══════════════════════════════════════════════════════════════
    chapter_contents = _merge_and_rerank(
        precise_results, vector_results,
        max_chunks_per_chapter=6,
        max_total_chunks=10,
    )

    # ═══════════════════════════════════════════════════════════════
    # 知识图谱关联：前置知识 + 相关公式
    # ═══════════════════════════════════════════════════════════════
    kg_path = []
    kg_formulas = []
    try:
        if matched_concepts:
            concept_name = matched_concepts[0]
            kg_path = kg.find_path(concept_name)
            detail = kg.get_concept_detail(concept_name)
            if detail:
                kg_formulas = detail.get("related_formulas", [])[:3]
        elif target_chapters:
            # 回退：尝试用章节名作为概念名
            kg_path = kg.find_path(target_chapters[0])
    except Exception as exc:
        retrieval_errors.append(f"knowledge_graph_query: {exc}")

    # concept_results 保持兼容格式（供下游 generator 使用）
    concept_results = []
    for ch_name, contents in chapter_contents.items():
        for content in contents[:2]:
            concept_results.append({
                "chapter": ch_name,
                "content": content[:150],
                "chunk_id": "",
            })

    # ═══════════════════════════════════════════════════════════════
    # 历史记忆
    # ═══════════════════════════════════════════════════════════════
    history_results = _load_history(book_name, target_chapters)

    return {
        "chapter_contents": chapter_contents,
        "concept_results": concept_results,
        "history_results": history_results,
        "knowledge_graph_path": kg_path,
        "knowledge_graph_formulas": kg_formulas,
        "matched_concepts": matched_concepts,
        "retrieval_status": "degraded" if retrieval_errors else "ok",
        "retrieval_error": "; ".join(dict.fromkeys(retrieval_errors)),
    }


# ── 第1层：KG 精确检索 ──────────────────────────────────────────

def _kg_precise_retrieval(kg, user_input: str) -> tuple[list[dict], list[str]]:
    """通过知识图谱精确命中概念，并提取其所在 chunk 及上下文窗口。

    返回: (precise_results, matched_concept_names)
    precise_results: [{chapter, chunk_id, text, is_direct_hit, source}]
    """
    if not kg._is_local:
        return [], []

    # Step 1: 从 query 中匹配概念（search_concept 已做模糊匹配）
    matched = kg.search_concept(user_input, k=3)
    if not matched:
        return [], []

    results = []
    matched_names = []
    for score, concept in matched:
        if score < 30:  # 置信度阈值，过滤弱匹配
            continue
        name = concept["canonical_name"]
        matched_names.append(name)
        # 取该概念出现的 chunk + 前后1个 chunk 窗口（最多3个命中位置）
        chunks = kg.get_concept_chunks(name, window=1, max_hits=3)
        for ch in chunks:
            results.append({
                "chapter": ch.get("chapter", ""),
                "chunk_id": ch.get("chunk_id", ""),
                "text": ch.get("text", ""),
                "section_title": ch.get("section_title", ""),
                "page_idx": ch.get("page_idx", -1),
                "is_direct_hit": ch.get("is_direct_hit", False),
                "source": "kg_precise",
            })

    return results, matched_names


# ── 第2层：向量检索（支持按 role 优先级过滤）──────────────────────

def _vector_retrieval(vs, user_input: str, *, intent: str = "qa",
                      book_name: str = "",
                      target_chapters: list[str],
                      precise_chapters: list[str], k: int = 3, top_n: int = 2) -> list[dict]:
    """向量语义检索。优先在精确命中的章节内搜索，按 intent → role 优先级过滤。"""
    results = []
    priority_roles = INTENT_ROLE_PRIORITY.get(intent, [])

    # 优先搜索范围：精确命中章节 > 用户指定章节 > 全库
    search_scope = []
    if precise_chapters:
        search_scope = [ch for ch in precise_chapters if ch]
    elif target_chapters:
        search_scope = target_chapters[:2]

    if search_scope:
        for ch in search_scope:
            docs, used_role = _search_chapter_with_role(vs, ch, user_input, k, priority_roles, book_name=book_name)
            for d in docs:
                results.append({
                    "chapter": ch,
                    "chunk_id": d.metadata.get("chunk_id", ""),
                    "text": d.page_content,
                    "section_title": "",
                    "page_idx": -1,
                    "is_direct_hit": False,
                    "source": f"vector({used_role})" if used_role else "vector",
                })
            # 例题额外做无过滤搜索：题干 chunk 可能被标为 reference/definition，
            # 纯 example 过滤会漏掉题干
            if used_role == "example":
                try:
                    extra_docs = vs.search_chapter(ch, user_input, k=k * 2, book_name=book_name)
                    for d in extra_docs:
                        results.append({
                            "chapter": ch,
                            "chunk_id": d.metadata.get("chunk_id", ""),
                            "text": d.page_content,
                            "section_title": "",
                            "page_idx": -1,
                            "is_direct_hit": False,
                            "source": "vector(example_boost)",
                        })
                except Exception:
                    pass
    else:
        # 全库搜索
        all_results, used_role = _search_all_with_role(vs, user_input, k, top_n, priority_roles, book_name=book_name)
        for ch_name, docs in all_results.items():
            for d in docs:
                results.append({
                    "chapter": ch_name,
                    "chunk_id": d.metadata.get("chunk_id", ""),
                    "text": d.page_content,
                    "section_title": "",
                    "page_idx": -1,
                    "is_direct_hit": False,
                    "source": f"vector({used_role})" if used_role else "vector",
                })
        # 全库 example 也做无过滤 boost
        if used_role == "example":
            try:
                extra_results = vs.search_all(user_input, k=k * 2, top_n=top_n, book_name=book_name)
                for ch_name, docs in extra_results.items():
                    for d in docs:
                        results.append({
                            "chapter": ch_name,
                            "chunk_id": d.metadata.get("chunk_id", ""),
                            "text": d.page_content,
                            "section_title": "",
                            "page_idx": -1,
                            "is_direct_hit": False,
                            "source": "vector(example_boost)",
                        })
            except Exception:
                pass

    return results


def _search_chapter_with_role(vs, chapter: str, query: str, k: int,
                               priority_roles: list[str], book_name: str = ""):
    """在指定章节内按 role 优先级搜索，无结果则回退到无过滤。"""
    for role in priority_roles:
        try:
            # langchain_chroma filter 格式: {"role": "definition"}
            docs = vs.search_chapter(chapter, query, k=k,
                                      filter={"role": role}, book_name=book_name)
            if docs:
                return docs, role
        except Exception:
            pass
    # 回退：无过滤搜索
    try:
        docs = vs.search_chapter(chapter, query, k=k, book_name=book_name)
        return docs, None
    except Exception:
        return [], None


def _search_all_with_role(vs, query: str, k: int, top_n: int,
                          priority_roles: list[str], book_name: str = ""):
    """全库按 role 优先级搜索，无结果则回退到无过滤。"""
    for role in priority_roles:
        try:
            results = vs.search_all(query, k=k, top_n=top_n,
                                    filter={"role": role}, book_name=book_name)
            if results:
                return results, role
        except Exception:
            pass
    # 回退：无过滤搜索
    try:
        results = vs.search_all(query, k=k, top_n=top_n, book_name=book_name)
        return results, None
    except Exception:
        return {}, None


# ── 第3层：合并去重 + 重排序 ────────────────────────────────────

def _merge_and_rerank(precise: list[dict], vector: list[dict],
                      *, max_chunks_per_chapter: int = 5,
                      max_total_chunks: int = 8) -> dict[str, list[str]]:
    """合并两层检索结果，去重后重排序，按章节组织。

    排序规则：
      1. KG 精确直接命中（is_direct_hit=True）排最前
      2. KG 精确上下文（is_direct_hit=False, source=kg_precise）次之
      3. 向量检索结果最后
    """
    all_items = []
    seen_text_hash = set()

    def _text_hash(text: str) -> str:
        return text[:80].strip().replace(" ", "").replace("\n", "")

    # 先放精确结果（高优先级）
    for item in precise:
        h = _text_hash(item["text"])
        if h not in seen_text_hash:
            seen_text_hash.add(h)
            priority = 0 if item.get("is_direct_hit") else 1
            all_items.append((priority, item))

    # 再放向量结果（去重）
    for item in vector:
        h = _text_hash(item["text"])
        if h not in seen_text_hash:
            seen_text_hash.add(h)
            all_items.append((2, item))

    # 按优先级排序
    all_items.sort(key=lambda x: x[0])

    # 按章节聚合，限制每章 chunk 数
    chapter_contents: dict[str, list[str]] = {}
    total = 0
    for priority, item in all_items:
        ch = item.get("chapter", "")
        if not ch:
            ch = "相关章节"
        if ch not in chapter_contents:
            chapter_contents[ch] = []
        if len(chapter_contents[ch]) >= max_chunks_per_chapter:
            continue
        if total >= max_total_chunks:
            break
        chapter_contents[ch].append(item["text"])
        total += 1

    return chapter_contents


# ── 历史记忆加载 ────────────────────────────────────────────────

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
