"""Controlled tools over textbook, KG, mistakes, and review data."""
from __future__ import annotations

from collections import Counter
from typing import Any

from config import PROGRESS_PATH
from graph.safe_retrieval import get_safe_kg, get_safe_vector_store
from memory.mistake_book import MistakeRecord, get_mistake_book

from backend.tools.registry import ToolContext, ToolRegistry, ToolResult, ToolSpec


def _as_int(value: Any, default: int, low: int = 1, high: int = 50) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(low, min(high, number))


def _record_summary(record: MistakeRecord) -> dict:
    sm2 = record.sm2 or {}
    return {
        "id": record.id,
        "question_text": record.question_text,
        "subject": record.subject,
        "chapter": record.chapter,
        "source": record.source,
        "tags": record.tags,
        "mistake_type": record.mistake_type,
        "difficulty": record.difficulty,
        "next_review": sm2.get("next_review"),
        "interval": sm2.get("interval"),
        "linked_concepts": record.linked_concepts,
    }


def search_textbook(context: ToolContext, args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query") or "").strip()
    if not query:
        return ToolResult(False, message="query is required")
    book_name = str(args.get("book_name") or context.book_name or "").strip()
    chapter = str(args.get("chapter") or "").strip()
    limit = _as_int(args.get("limit"), 5, high=12)

    vs, error = get_safe_vector_store()
    if error:
        return ToolResult(False, data=[], message=f"vector store unavailable: {error}")

    snippets: list[dict] = []
    if chapter:
        docs = vs.search_chapter(chapter, query, k=limit, book_name=book_name)
        for doc in docs:
            snippets.append({
                "chapter": chapter,
                "chunk_id": doc.metadata.get("chunk_id", ""),
                "role": doc.metadata.get("role", ""),
                "page": doc.metadata.get("page_idx", doc.metadata.get("page", "")),
                "text": doc.page_content[:1200],
            })
    else:
        results = vs.search_all(query, k=min(3, limit), top_n=limit, book_name=book_name)
        for ch_name, docs in results.items():
            for doc in docs:
                snippets.append({
                    "chapter": ch_name,
                    "chunk_id": doc.metadata.get("chunk_id", ""),
                    "role": doc.metadata.get("role", ""),
                    "page": doc.metadata.get("page_idx", doc.metadata.get("page", "")),
                    "text": doc.page_content[:1200],
                })
                if len(snippets) >= limit:
                    break
            if len(snippets) >= limit:
                break

    return ToolResult(True, data={"book_name": book_name, "snippets": snippets})


def search_concepts(context: ToolContext, args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query") or "").strip()
    if not query:
        return ToolResult(False, message="query is required")
    book_name = str(args.get("book_name") or context.book_name or "").strip()
    limit = _as_int(args.get("limit"), 5, high=15)

    kg, error = get_safe_kg(book_name)
    if error:
        return ToolResult(False, data=[], message=f"knowledge graph unavailable: {error}")

    matches = []
    for score, concept in kg.search_concept(query, k=limit):
        name = concept.get("canonical_name") or concept.get("name") or ""
        detail = kg.get_concept_detail(name) if name else None
        matches.append({
            "name": name,
            "score": score,
            "aliases": concept.get("aliases", []),
            "definition": (detail or {}).get("definition", concept.get("definition", "")),
            "related_formulas": (detail or {}).get("related_formulas", [])[:5],
            "path": kg.find_path(name) if name else [],
        })
    return ToolResult(True, data={"book_name": book_name, "concepts": matches})


def get_due_mistakes(context: ToolContext, args: dict[str, Any]) -> ToolResult:
    book_name = str(args.get("book_name") or context.book_name or "default").strip()
    subject = str(args.get("subject") or context.subject or "").strip()
    limit = _as_int(args.get("limit"), 10, high=50)
    mb = get_mistake_book(book_name, str(PROGRESS_PATH))
    records = mb.get_due(subject=subject or None)[:limit]
    return ToolResult(True, data={"book_name": book_name, "subject": subject, "mistakes": [_record_summary(r) for r in records]})


def get_mistake_stats(context: ToolContext, args: dict[str, Any]) -> ToolResult:
    book_name = str(args.get("book_name") or context.book_name or "default").strip()
    subject = str(args.get("subject") or context.subject or "").strip()
    mb = get_mistake_book(book_name, str(PROGRESS_PATH))
    return ToolResult(True, data={
        "book_name": book_name,
        "subject": subject,
        "stats": mb.get_stats(subject=subject or None),
        "weak_points": mb.get_weak_points(subject=subject or None, top_n=_as_int(args.get("limit"), 8, high=30)),
    })


def build_review_plan(context: ToolContext, args: dict[str, Any]) -> ToolResult:
    book_name = str(args.get("book_name") or context.book_name or "default").strip()
    subject = str(args.get("subject") or context.subject or "").strip()
    limit = _as_int(args.get("limit"), 8, high=20)

    mb = get_mistake_book(book_name, str(PROGRESS_PATH))
    stats = mb.get_stats(subject=subject or None)
    due = mb.get_due(subject=subject or None)
    weak_points = mb.get_weak_points(subject=subject or None, top_n=limit)

    concept_queue = []
    concept_stats = {}
    try:
        from knowledge.concept_memory import ConceptMemory

        cm = ConceptMemory(book_name)
        concept_queue = cm.get_review_queue(limit=limit)
        concept_stats = cm.get_stats()
    except Exception as exc:
        concept_stats = {"error": str(exc)}

    mistake_items = [
        {
            "type": "mistake",
            "priority": 100 - index,
            "reason": "due_review",
            "item": _record_summary(record),
        }
        for index, record in enumerate(due[:limit])
    ]
    concept_items = [
        {
            "type": "concept",
            "priority": 70 - index,
            "reason": item.get("reason", "review_queue"),
            "item": item,
        }
        for index, item in enumerate(concept_queue[:limit])
    ]
    weak_items = [
        {
            "type": "weak_point",
            "priority": 50 - index,
            "reason": "mistake_statistics",
            "item": item,
        }
        for index, item in enumerate(weak_points[:limit])
    ]

    plan = sorted(mistake_items + concept_items + weak_items, key=lambda x: x["priority"], reverse=True)[:limit]
    return ToolResult(True, data={
        "book_name": book_name,
        "subject": subject,
        "summary": {
            "due_mistakes": len(due),
            "total_mistakes": stats.get("total", 0),
            "weak_points": len(weak_points),
            "concept_stats": concept_stats,
        },
        "plan": plan,
    })


def link_concepts(context: ToolContext, args: dict[str, Any]) -> ToolResult:
    text = str(args.get("text") or args.get("query") or "").strip()
    if not text:
        return ToolResult(False, message="text is required")
    return search_concepts(context, {"query": text, "limit": args.get("limit", 5), "book_name": args.get("book_name")})


def propose_add_mistake(context: ToolContext, args: dict[str, Any]) -> ToolResult:
    question_text = str(args.get("question_text") or args.get("question") or "").strip()
    if not question_text:
        return ToolResult(False, message="question_text is required")
    payload = {
        "question_text": question_text,
        "user_answer": str(args.get("user_answer") or ""),
        "correct_answer": str(args.get("correct_answer") or ""),
        "source": str(args.get("source") or "agent_proposal"),
        "subject": str(args.get("subject") or context.subject or ""),
        "chapter": str(args.get("chapter") or ""),
        "tags": str(args.get("tags") or ""),
        "mistake_type": args.get("mistake_type") if isinstance(args.get("mistake_type"), list) else [],
        "difficulty": _as_int(args.get("difficulty"), 3, high=5),
        "explanation": str(args.get("explanation") or ""),
    }
    return ToolResult(
        True,
        data={"preview": payload},
        message="pending user confirmation",
        pending_action={"type": "add_mistake", "payload": payload},
    )


def propose_concept_review(context: ToolContext, args: dict[str, Any]) -> ToolResult:
    name = str(args.get("name") or args.get("concept") or "").strip()
    if not name:
        return ToolResult(False, message="name is required")
    payload = {
        "name": name,
        "quality": _as_int(args.get("quality"), 4, low=0, high=5),
        "note": str(args.get("note") or "agent_proposal"),
        "book_name": str(args.get("book_name") or context.book_name or ""),
    }
    return ToolResult(
        True,
        data={"preview": payload},
        message="pending user confirmation",
        pending_action={"type": "mark_concept_reviewed", "payload": payload},
    )


def summarize_learning_evidence(tool_outputs: list[dict]) -> dict:
    calls = Counter(item.get("tool") for item in tool_outputs)
    pending = [item.get("result", {}).get("pending_action") for item in tool_outputs if item.get("result", {}).get("pending_action")]
    return {
        "tool_counts": dict(calls),
        "pending_actions": pending,
        "has_textbook_evidence": any(item.get("tool") == "search_textbook" and item.get("result", {}).get("data", {}).get("snippets") for item in tool_outputs),
        "has_review_evidence": any(item.get("tool") in {"get_due_mistakes", "build_review_plan", "get_mistake_stats"} for item in tool_outputs),
    }


def register_learning_tools(registry: ToolRegistry):
    registry.register(ToolSpec(
        name="search_textbook",
        description="Search textbook chunks from the local vector store.",
        parameters={"query": "str", "book_name": "str?", "chapter": "str?", "limit": "int?"},
        read_only=True,
        handler=search_textbook,
    ))
    registry.register(ToolSpec(
        name="search_concepts",
        description="Search local knowledge graph concepts and related formulas.",
        parameters={"query": "str", "book_name": "str?", "limit": "int?"},
        read_only=True,
        handler=search_concepts,
    ))
    registry.register(ToolSpec(
        name="link_concepts",
        description="Link free text to likely knowledge graph concepts.",
        parameters={"text": "str", "book_name": "str?", "limit": "int?"},
        read_only=True,
        handler=link_concepts,
    ))
    registry.register(ToolSpec(
        name="get_due_mistakes",
        description="Read due mistake reviews from the SM-2 queue.",
        parameters={"book_name": "str?", "subject": "str?", "limit": "int?"},
        read_only=True,
        handler=get_due_mistakes,
    ))
    registry.register(ToolSpec(
        name="get_mistake_stats",
        description="Read mistake statistics and weak points.",
        parameters={"book_name": "str?", "subject": "str?", "limit": "int?"},
        read_only=True,
        handler=get_mistake_stats,
    ))
    registry.register(ToolSpec(
        name="build_review_plan",
        description="Build a read-only review plan from due mistakes, weak points, and concept memory.",
        parameters={"book_name": "str?", "subject": "str?", "limit": "int?"},
        read_only=True,
        handler=build_review_plan,
    ))
    registry.register(ToolSpec(
        name="propose_add_mistake",
        description="Prepare an add-mistake action for user confirmation; does not write data.",
        parameters={"question_text": "str", "user_answer": "str?", "correct_answer": "str?", "subject": "str?", "chapter": "str?"},
        read_only=True,
        handler=propose_add_mistake,
    ))
    registry.register(ToolSpec(
        name="propose_concept_review",
        description="Prepare a concept-review action for user confirmation; does not write data.",
        parameters={"name": "str", "quality": "int?", "note": "str?"},
        read_only=True,
        handler=propose_concept_review,
    ))
