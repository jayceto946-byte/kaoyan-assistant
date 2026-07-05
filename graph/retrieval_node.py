"""Hybrid retrieval node: KG exact hits, role-aware vector search, rerank, and debug metadata."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from config import PROGRESS_PATH
from graph.safe_retrieval import get_safe_kg, get_safe_vector_store

INTENT_ROLE_PRIORITY: dict[str, list[str]] = {
    "definition": ["definition", "theorem", "property", "example", "derivation"],
    "formula": ["definition", "property", "derivation", "example"],
    "property": ["property", "theorem", "definition", "example"],
    "derivation": ["derivation", "theorem", "proof", "definition"],
    "comparison": ["definition", "property", "example"],
    "application": ["example", "algorithm", "exercise", "derivation"],
    "teach": ["definition", "example", "algorithm", "property", "derivation"],
    "summarize": ["definition", "property", "theorem", "derivation"],
    "quiz": ["example", "exercise", "derivation"],
    "plan": ["definition", "algorithm", "property"],
    "cross_chapter": ["definition", "property", "theorem"],
    "qa": ["definition", "theorem", "property", "example", "derivation"],
}

BOOK_ROLE_RANK = {"core": 0, "reference": 1, "": 2}

ROLE_RANK = {
    "definition": 0,
    "theorem": 1,
    "property": 2,
    "derivation": 3,
    "proof": 4,
    "algorithm": 5,
    "example": 6,
    "exercise": 7,
    "reference": 8,
    "": 9,
}

TOC_SECTION_MARKERS = {
    "(no title)",
    "\u76ee\u5f55",
    "\u672c\u7ae0\u5b66\u4e60\u8981\u70b9",
    "\u4e60\u9898",
    "\u601d\u8003\u9898",
    "\u53c2\u8003\u6587\u732e",
    "\u9644\u5f55",
    "table of contents",
    "toc",
}


def retrieve_node(state: dict) -> dict:
    target_chapters = state.get("target_chapters", [])
    user_input = state.get("user_input", "")
    book_name = state.get("book_name", "default")
    intent = state.get("intent", "qa")

    if not state.get("use_textbook_context", True):
        return {
            "chapter_contents": {},
            "retrieval_debug_items": [],
            "concept_results": [],
            "history_results": [],
            "knowledge_graph_path": [],
            "knowledge_graph_formulas": [],
            "matched_concepts": [],
            "retrieval_status": "ordinary_qa",
            "retrieval_error": "",
        }

    retrieval_errors: list[str] = []
    if state.get("retrieval_error"):
        retrieval_errors.append(str(state.get("retrieval_error")))

    vs, vector_error = get_safe_vector_store()
    kg, kg_error = get_safe_kg(book_name)
    if vector_error:
        retrieval_errors.append(f"vector_store: {vector_error}")
    if kg_error:
        retrieval_errors.append(f"knowledge_graph: {kg_error}")

    precise_results, matched_concepts = _kg_precise_retrieval(kg, user_input, intent=intent)
    vector_results = _vector_retrieval(
        vs,
        user_input,
        intent=intent,
        book_name=book_name,
        target_chapters=target_chapters,
        precise_chapters=list({r["chapter"] for r in precise_results if r.get("chapter")}),
        k=3,
        top_n=2,
    )
    chapter_contents, retrieval_debug_items = _merge_and_rerank(
        precise_results,
        vector_results,
        max_chunks_per_chapter=6,
        max_total_chunks=10,
        include_metadata=True,
    )

    kg_path: list[str] = []
    kg_formulas: list[dict] = []
    try:
        if matched_concepts:
            concept_name = matched_concepts[0]
            kg_path = kg.find_path(concept_name)
            detail = kg.get_concept_detail(concept_name)
            if detail:
                kg_formulas = detail.get("related_formulas", [])[:3]
        elif target_chapters:
            kg_path = kg.find_path(target_chapters[0])
    except Exception as exc:
        retrieval_errors.append(f"knowledge_graph_query: {exc}")

    concept_results = []
    debug_by_text = {item.get("preview", ""): item for item in retrieval_debug_items}
    for ch_name, contents in chapter_contents.items():
        for content in contents[:2]:
            debug = _find_debug_for_content(content, debug_by_text)
            concept_results.append({
                "chapter": ch_name,
                "content": content[:150],
                "chunk_id": debug.get("chunk_id", "") if debug else "",
            })

    history_results = _load_history(book_name, target_chapters)

    return {
        "chapter_contents": chapter_contents,
        "retrieval_debug_items": retrieval_debug_items,
        "concept_results": concept_results,
        "history_results": history_results,
        "knowledge_graph_path": kg_path,
        "knowledge_graph_formulas": kg_formulas,
        "matched_concepts": matched_concepts,
        "retrieval_status": "degraded" if retrieval_errors else "ok",
        "retrieval_error": "; ".join(dict.fromkeys(retrieval_errors)),
    }


def _find_debug_for_content(content: str, debug_by_preview: dict[str, dict]) -> dict | None:
    for preview, item in debug_by_preview.items():
        if preview and content.startswith(preview):
            return item
    return None


def _core_query_terms(user_input: str) -> list[str]:
    text = user_input.strip()
    for suffix in (
        "\u662f\u4ec0\u4e48",
        "\u662f\u4ec0\u4e48\u610f\u601d",
        "\u7684\u5b9a\u4e49",
        "\u5b9a\u4e49",
        "\u6709\u4ec0\u4e48\u6027\u8d28",
        "\u57fa\u672c\u601d\u60f3\u662f\u4ec0\u4e48",
        "\u8bb2\u4e00\u4e0b",
        "\u8bf7\u89e3\u91ca",
        "\uff1f",
        "?",
        "\u3002",
    ):
        text = text.replace(suffix, " ")
    parts = re.findall(r"[A-Za-z0-9_.+-]+|[\u4e00-\u9fff]{2,}", text)
    return [p.strip() for p in parts if p.strip()]


def _rank_concept_matches(matches: list[tuple[float, dict]], user_input: str, intent: str = "qa") -> list[tuple[float, dict]]:
    q = user_input.strip().lower()
    terms = _core_query_terms(user_input)
    role_boost = set(INTENT_ROLE_PRIORITY.get(intent, []))

    def score(item: tuple[float, dict]) -> tuple[float, int, int]:
        base, concept = item
        name = str(concept.get("canonical_name") or "")
        aliases = [str(a) for a in concept.get("aliases", [])]
        names = [name] + aliases
        adjusted = float(base)
        if any(q == n.lower() for n in names):
            adjusted += 60
        if any(n and n.lower() in q for n in names):
            adjusted += 35
        if any(term == name for term in terms):
            adjusted += 40
        partial_terms = [term for term in terms if term and term in name and term != name]
        if partial_terms:
            best_partial = max(partial_terms, key=len)
            adjusted -= max(0, len(name) - len(best_partial)) * 1.5
        if role_boost and role_boost.intersection(set(concept.get("roles", []))):
            adjusted += 12
        return adjusted, -len(name), int(concept.get("occurrence_count", 0))

    return sorted(matches, key=score, reverse=True)


def _looks_like_toc_chunk(item: dict) -> bool:
    section = str(item.get("section_title") or "")
    section_lc = section.strip().lower()
    text = str(item.get("text") or "")
    if section_lc in TOC_SECTION_MARKERS:
        return True
    if any(marker in section_lc for marker in ("\u76ee\u5f55", "\u672c\u7ae0\u5b66\u4e60\u8981\u70b9", "\u4e60\u9898", "table of contents")):
        return True
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False
    joined = " ".join(lines[:8])
    chapter_markers = sum(1 for line in lines[:14] if "\u7b2c" in line and ("\u7ae0" in line or "\u8282" in line))
    page_number_markers = len(re.findall(r"\s\d{1,3}(\s|$)", joined))
    return chapter_markers >= 3 and page_number_markers >= 3


def _kg_precise_retrieval(kg, user_input: str, intent: str = "qa") -> tuple[list[dict], list[str]]:
    if not getattr(kg, "_is_local", False):
        return [], []

    matched = _rank_concept_matches(kg.search_concept(user_input, k=8), user_input, intent=intent)[:3]
    if not matched:
        return [], []

    results: list[dict] = []
    matched_names: list[str] = []
    for score, concept in matched:
        if score < 30:
            continue
        name = concept["canonical_name"]
        matched_names.append(name)
        chunks = kg.get_concept_chunks(name, window=1, max_hits=3)
        chunks = sorted(chunks, key=lambda ch: (_looks_like_toc_chunk(ch), not ch.get("is_direct_hit", False), ROLE_RANK.get(ch.get("role", ""), 9)))
        for ch in chunks:
            if _looks_like_toc_chunk(ch) and not ch.get("is_direct_hit", False):
                continue
            results.append({
                "chapter": ch.get("chapter", ""),
                "chunk_id": ch.get("chunk_id", ""),
                "text": ch.get("text", ""),
                "section_title": ch.get("section_title", ""),
                "page_idx": ch.get("page_idx", -1),
                "is_direct_hit": ch.get("is_direct_hit", False),
                "role": ch.get("role", ""),
                "source": "kg_precise",
            })

    return results, matched_names


def _vector_retrieval(vs, user_input: str, *, intent: str = "qa", book_name: str = "", target_chapters: list[str], precise_chapters: list[str], k: int = 3, top_n: int = 2) -> list[dict]:
    results: list[dict] = []
    priority_roles = INTENT_ROLE_PRIORITY.get(intent, [])
    search_scope: list[str] = []
    if precise_chapters:
        search_scope = [ch for ch in precise_chapters if ch]
    elif target_chapters:
        search_scope = target_chapters[:2]

    if search_scope:
        for ch in search_scope:
            docs, used_role = _search_chapter_with_role(vs, ch, user_input, k, priority_roles, book_name=book_name)
            for d in docs:
                results.append(_doc_to_item(d, ch, f"vector({used_role})" if used_role else "vector"))
            if used_role == "example":
                try:
                    for d in vs.search_chapter(ch, user_input, k=k * 2, book_name=book_name):
                        results.append(_doc_to_item(d, ch, "vector(example_boost)"))
                except Exception:
                    pass
    else:
        all_results, used_role = _search_all_with_role(vs, user_input, k, top_n, priority_roles, book_name=book_name)
        for ch_name, docs in all_results.items():
            for d in docs:
                results.append(_doc_to_item(d, ch_name, f"vector({used_role})" if used_role else "vector"))
        if used_role == "example":
            try:
                for ch_name, docs in vs.search_all(user_input, k=k * 2, top_n=top_n, book_name=book_name).items():
                    for d in docs:
                        results.append(_doc_to_item(d, ch_name, "vector(example_boost)"))
            except Exception:
                pass
    return results


def _doc_to_item(doc, chapter: str, source: str) -> dict:
    meta = getattr(doc, "metadata", {}) or {}
    return {
        "chapter": chapter,
        "chunk_id": meta.get("chunk_id", ""),
        "text": getattr(doc, "page_content", ""),
        "section_title": meta.get("section_title", ""),
        "page_idx": meta.get("page_idx", -1),
        "is_direct_hit": False,
        "role": meta.get("role", ""),
        "book_role": meta.get("book_role", ""),
        "rag_priority": float(meta.get("rag_priority") or 1.0),
        "subject": meta.get("subject", ""),
        "source": source,
    }


def _search_chapter_with_role(vs, chapter: str, query: str, k: int, priority_roles: list[str], book_name: str = ""):
    for role in priority_roles:
        try:
            docs = vs.search_chapter(chapter, query, k=k, filter={"role": role}, book_name=book_name)
            if docs:
                return docs, role
        except Exception:
            pass
    try:
        return vs.search_chapter(chapter, query, k=k, book_name=book_name), None
    except Exception:
        return [], None


def _search_all_with_role(vs, query: str, k: int, top_n: int, priority_roles: list[str], book_name: str = ""):
    for role in priority_roles:
        try:
            results = vs.search_all(query, k=k, top_n=top_n, filter={"role": role}, book_name=book_name)
            if results:
                return results, role
        except Exception:
            pass
    try:
        return vs.search_all(query, k=k, top_n=top_n, book_name=book_name), None
    except Exception:
        return {}, None


def _merge_and_rerank(precise: list[dict], vector: list[dict], *, max_chunks_per_chapter: int = 5, max_total_chunks: int = 8, include_metadata: bool = False):
    all_items: list[tuple[int, dict]] = []
    seen_text_hash: set[str] = set()

    def text_hash(text: str) -> str:
        return text[:80].strip().replace(" ", "").replace("\n", "")

    for item in precise:
        h = text_hash(item.get("text", ""))
        if h and h not in seen_text_hash:
            seen_text_hash.add(h)
            priority = 0 if item.get("is_direct_hit") else 1
            all_items.append((priority, item))

    for item in vector:
        h = text_hash(item.get("text", ""))
        if h and h not in seen_text_hash:
            seen_text_hash.add(h)
            all_items.append((2, item))

    def rank(pair: tuple[int, dict]) -> tuple[Any, ...]:
        priority, item = pair
        return (
            priority,
            _looks_like_toc_chunk(item),
            BOOK_ROLE_RANK.get(item.get("book_role", ""), 2),
            ROLE_RANK.get(item.get("role", ""), 9),
            item.get("page_idx", 999999),
        )

    all_items.sort(key=rank)
    chapter_contents: dict[str, list[str]] = {}
    debug_items: list[dict] = []
    total = 0
    for _, item in all_items:
        chapter = item.get("chapter") or "\u76f8\u5173\u7ae0\u8282"
        chapter_contents.setdefault(chapter, [])
        if len(chapter_contents[chapter]) >= max_chunks_per_chapter:
            continue
        if total >= max_total_chunks:
            break
        text = item.get("text", "")
        chapter_contents[chapter].append(text)
        debug_items.append({
            "rank": total + 1,
            "chapter": chapter,
            "chunk_id": item.get("chunk_id", ""),
            "source": item.get("source", ""),
            "role": item.get("role", ""),
            "book_role": item.get("book_role", ""),
            "rag_priority": item.get("rag_priority", 1.0),
            "section_title": item.get("section_title", ""),
            "page_idx": item.get("page_idx", -1),
            "is_direct_hit": bool(item.get("is_direct_hit", False)),
            "is_toc_like": _looks_like_toc_chunk(item),
            "preview": text[:180],
        })
        total += 1

    if include_metadata:
        return chapter_contents, debug_items
    return chapter_contents


def _load_history(book_name: str, chapters: list[str]) -> list[dict]:
    results: list[dict] = []
    progress_dir = Path(PROGRESS_PATH) / book_name
    weakness_file = progress_dir / "weakness.json"
    if weakness_file.exists():
        with open(weakness_file, "r", encoding="utf-8") as f:
            for item in json.load(f)[-10:]:
                results.append({"type": "weakness", "chapter": item})
    quiz_file = progress_dir / "quiz_history.json"
    if quiz_file.exists():
        with open(quiz_file, "r", encoding="utf-8") as f:
            for q in json.load(f)[-10:]:
                results.append({
                    "type": "quiz",
                    "chapter": q.get("chapter", ""),
                    "correct": q.get("correct", False),
                    "question": q.get("question", "")[:80],
                })
    return results
