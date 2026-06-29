"""Knowledge Graph API — 知识图谱

包装 knowledge/knowledge_graph.py 和 knowledge/kg_visualizer.py
"""
from pathlib import Path

from fastapi import APIRouter

from backend.schemas import KGGraphOut, KGRefreshOut
from config import PROGRESS_PATH

router = APIRouter(prefix="/kg", tags=["knowledge-graph"])


def _kg_html_path(book_name: str) -> Path:
    return Path(PROGRESS_PATH) / book_name / "kg_graph.html"


@router.get("/graph")
def get_kg_graph(book_name: str = ""):
    """获取知识图谱 HTML

    如果已有缓存，直接返回 HTML 内容；
    如果没有，返回提示信息，前端引导用户点击刷新。
    """
    if not book_name:
        return KGGraphOut(book_name="", exists=False, html_content="", concept_count=0)

    html_path = _kg_html_path(book_name)
    if html_path.exists():
        try:
            html = html_path.read_text(encoding="utf-8")
            # 从 knowledge_graph.py 获取概念数
            from knowledge.knowledge_graph import get_kg
            kg = get_kg(book_name)
            graph = kg.graph
            count = len(graph) if graph else 0
            return KGGraphOut(
                book_name=book_name,
                exists=True,
                html_content=html,
                concept_count=count,
            )
        except Exception as e:
            return KGGraphOut(
                book_name=book_name,
                exists=False,
                html_content=f"",
                concept_count=0,
            )

    return KGGraphOut(
        book_name=book_name,
        exists=False,
        html_content="",
        concept_count=0,
    )


@router.post("/refresh")
def refresh_kg(book_name: str = ""):
    """重新生成知识图谱"""
    if not book_name:
        return KGRefreshOut(success=False, message="请先选择教材", html_content="", concept_count=0)

    html_path = _kg_html_path(book_name)
    if html_path.exists():
        html_path.unlink()

    try:
        from knowledge.knowledge_graph import get_kg
        from knowledge.kg_visualizer import KGVisualizer

        kg = get_kg(book_name)
        graph = kg.graph
        if not graph:
            return KGRefreshOut(
                success=False,
                message="知识图谱为空",
                html_content="<p>知识图谱为空</p>",
                concept_count=0,
            )

        viz = KGVisualizer(book_name)
        definitions, _ = viz.enrich_definitions(graph, vector_store=None)
        html = viz.generate_html(graph, definitions, kg_instance=kg)
        viz.save_html(html)
        count = len(graph)

        return KGRefreshOut(
            success=True,
            message=f"已刷新 ({count} 概念)",
            html_content=html,
            concept_count=count,
        )
    except Exception as e:
        return KGRefreshOut(
            success=False,
            message=f"生成失败: {e}",
            html_content="",
            concept_count=0,
        )



@router.get("/concept-wiki")
def get_concept_wiki(name: str, book_name: str = ""):
    """Return a compact concept wiki card for inline chat interactions."""
    if not book_name:
        return {"success": False, "message": "请先选择教材", "data": None}
    try:
        from knowledge.knowledge_graph import get_kg

        kg = get_kg(book_name)
        wiki = kg.get_concept_wiki(name)
        if not wiki:
            return {"success": False, "message": "未找到概念", "data": None}
        return {"success": True, "data": wiki}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}




def _parse_dt(value: str):
    from datetime import datetime
    try:
        return datetime.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def _days_since(value: str) -> int | None:
    from datetime import datetime
    dt = _parse_dt(value)
    if not dt:
        return None
    return max(0, (datetime.now() - dt).days)


def _build_concept_review_plan(book_name: str, concepts: dict, strict_exposures: list[dict], concept_counts, mistake_weak_points: list[dict], subject: str = "", limit: int = 8) -> list[dict]:
    """Build actionable concept review cards from memory, mistakes, and KG metadata."""
    from config import PROGRESS_PATH
    from memory.mistake_book import get_mistake_book

    weak_names = {name for name, info in concepts.items() if info.get("weak_flag")}
    mistake_counts = {item.get("name", ""): int(item.get("count", 0) or 0) for item in mistake_weak_points}
    candidate_names = set(weak_names) | {name for name, _ in concept_counts.most_common(12)} | {name for name, count in mistake_counts.items() if count > 0}

    now_items = []
    try:
        mb = get_mistake_book(book_name, str(PROGRESS_PATH))
        mistake_records = mb.list_all(subject=subject or None, limit=1000)
    except Exception:
        mistake_records = []

    for name in candidate_names:
        if not name:
            continue
        info = concepts.get(name, {})
        exposure_count = int(info.get("exposure_count", 0) or concept_counts.get(name, 0) or 0)
        days_since_seen = _days_since(info.get("last_exposed_at", ""))
        days_since_review = _days_since(info.get("last_reviewed_at", ""))
        related_mistakes = []
        for record in mistake_records:
            linked_names = [str(c.get("name", "")) for c in getattr(record, "linked_concepts", [])]
            haystack = "\n".join([
                getattr(record, "question_text", ""),
                getattr(record, "ocr_text", ""),
                getattr(record, "explanation", ""),
                " ".join(getattr(record, "tags", []) or []),
                " ".join(linked_names),
            ])
            if name in haystack:
                related_mistakes.append(_mistake_summary(record))
            if len(related_mistakes) >= 50:
                break

        recent_questions = []
        seen_questions = set()
        for e in reversed(strict_exposures):
            if e.get("concept") != name:
                continue
            question = (e.get("question") or "").strip()
            if not question or question in seen_questions:
                continue
            seen_questions.add(question)
            recent_questions.append({
                "question": question,
                "source": "mistake" if e.get("source") == "mistake" or e.get("intent") == "mistake" else "qa",
                "timestamp": e.get("timestamp", ""),
                "weak": bool(e.get("weak")),
                "mistake_id": next(
                    (
                        record.id
                        for record in mistake_records
                        if question and question in "\n".join([record.question_text, record.ocr_text, record.explanation])
                    ),
                    "",
                ),
            })
            if len(recent_questions) >= 3:
                break

        textbook_snippets = []
        source_chapters = [str(ch) for ch in info.get("source_chapters", []) if str(ch).strip()]
        for ch in source_chapters[:4]:
            textbook_snippets.append({"type": "chapter", "text": ch, "chapter": ch})

        reasons = []
        priority = 0
        if info.get("weak_flag") or name in weak_names:
            reasons.append("已标记为薄弱概念")
            priority += 45
        if related_mistakes:
            reasons.append(f"关联 {len(related_mistakes)} 道错题")
            priority += 30 + len(related_mistakes) * 4
        elif mistake_counts.get(name, 0):
            reasons.append(f"错题统计出现 {mistake_counts[name]} 次")
            priority += 25
        if days_since_seen is not None and days_since_seen >= 7:
            reasons.append(f"{days_since_seen} 天未接触")
            priority += min(30, days_since_seen)
        if exposure_count >= 2:
            reasons.append(f"累计接触 {exposure_count} 次")
            priority += min(15, exposure_count * 2)
        if days_since_review is None:
            reasons.append("还没有明确复习记录")
            priority += 8
        elif days_since_review >= 7:
            reasons.append(f"上次复习已过 {days_since_review} 天")
            priority += min(20, days_since_review)
        if recent_questions:
            priority += 4

        if not reasons:
            continue

        now_items.append({
            "name": name,
            "priority": priority,
            "reasons": reasons[:4],
            "days_since_seen": days_since_seen,
            "days_since_review": days_since_review,
            "exposure_count": exposure_count,
            "mastery_level": info.get("mastery_level", 0),
            "weak": bool(info.get("weak_flag")),
            "recent_questions": recent_questions,
            "related_mistakes": related_mistakes,
            "textbook_snippets": textbook_snippets[:3],
        })

    now_items.sort(key=lambda item: (item["priority"], item["exposure_count"]), reverse=True)
    return now_items[:limit]

def _mistake_summary(record) -> dict:
    sm2 = getattr(record, "sm2", {}) or {}
    return {
        "id": record.id,
        "question_text": record.question_text,
        "source": record.source,
        "subject": record.subject,
        "chapter": record.chapter,
        "tags": record.tags,
        "mistake_type": record.mistake_type,
        "next_review": sm2.get("next_review"),
        "interval": sm2.get("interval"),
        "review_history": record.review_history,
        "linked_concepts": record.linked_concepts,
    }
@router.get("/learning-summary")
def get_learning_summary(book_name: str = "", subject: str = "", limit: int = 30):
    """Return strict concept memory activity plus mistake weak-point context."""
    if not book_name:
        return {"success": False, "message": "\u8bf7\u5148\u9009\u62e9\u6559\u6750", "data": None}
    try:
        from collections import Counter, defaultdict
        from knowledge.concept_memory import ConceptMemory
        from memory.mistake_book import get_mistake_book

        generic_alias_terms = {
            "\u65b9\u6cd5", "\u6b65\u9aa4", "\u8fed\u4ee3", "\u8fed\u4ee3\u6b65\u9aa4", "\u7a0b\u5e8f\u6846\u56fe", "\u539f\u7406", "\u8fc7\u7a0b", "\u7b97\u6cd5", "\u7ea6\u675f", "\u4f18\u5316", "\u4f18\u5316\u65b9\u6cd5", "\u6700\u4f18\u5316\u65b9\u6cd5", "\u95ee\u9898", "\u6761\u4ef6",
            "method", "step", "steps", "algorithm",
        }

        def is_strict(e: dict, concepts: dict) -> bool:
            try:
                if float(e.get("confidence", 0)) < 0.999:
                    return False
            except (TypeError, ValueError):
                return False
            name = str(e.get("concept", "")).strip()
            question = str(e.get("question", "")).lower()
            if not name or not question:
                return False
            link_source = str(e.get("link_source", ""))
            if (e.get("source") == "mistake" or e.get("intent") == "mistake") and link_source.startswith("mistake_"):
                return True
            info = concepts.get(name, {})
            aliases = [str(a).strip() for a in info.get("aliases", []) if str(a).strip()]
            direct_terms = [name, *[a for a in aliases if a not in generic_alias_terms]]
            return any(term and term.lower() in question for term in direct_terms)

        cm = ConceptMemory(book_name)
        data = cm._data
        raw_exposures = list(data.get("exposures", []))
        concepts = data.get("concepts", {})
        strict_exposures = [e for e in raw_exposures if is_strict(e, concepts)]
        recent_exposures = strict_exposures[-limit:]
        strict_names = {e.get("concept", "") for e in strict_exposures if e.get("concept")}

        concept_counts = Counter(e.get("concept", "") for e in strict_exposures if e.get("concept"))
        source_counts = Counter(e.get("source", "qa") for e in strict_exposures)
        daily = defaultdict(lambda: {"qa": 0, "mistake": 0, "total": 0})
        for e in strict_exposures:
            day = (e.get("timestamp", "") or "")[:10] or "unknown"
            source = "mistake" if e.get("source") == "mistake" or e.get("intent") == "mistake" else "qa"
            daily[day][source] += 1
            daily[day]["total"] += 1

        question_map = {}
        question_order = []
        for e in strict_exposures:
            question = (e.get("question") or "").strip()
            if not question:
                continue
            source = "mistake" if e.get("source") == "mistake" or e.get("intent") == "mistake" else "qa"
            key = (source, question)
            if key not in question_map:
                question_map[key] = {
                    "question": question,
                    "intent": e.get("intent", "qa"),
                    "source": source,
                    "weak": bool(e.get("weak")),
                    "timestamp": e.get("timestamp", ""),
                    "concepts": [],
                }
                question_order.append(key)
            item = question_map[key]
            item["timestamp"] = max(item.get("timestamp", ""), e.get("timestamp", ""))
            item["weak"] = item["weak"] or bool(e.get("weak"))
            concept = e.get("concept")
            if concept and all(c.get("name") != concept for c in item["concepts"]):
                item["concepts"].append({
                    "name": concept,
                    "confidence": e.get("confidence", 0),
                    "weak": bool(e.get("weak")),
                    "source": source,
                    "evidence": e.get("evidence", ""),
                })

        recent_questions = [question_map[k] for k in question_order]
        recent_questions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        recent_questions = recent_questions[:limit]

        weak = []
        for name, info in concepts.items():
            if name in strict_names and info.get("weak_flag"):
                weak.append({"name": name, **info})
        weak.sort(key=lambda x: x.get("last_weak_at", x.get("last_exposed_at", "")), reverse=True)

        review_queue = [item for item in cm.get_review_queue(limit=30) if item.get("name") in strict_names][:12]

        try:
            mb = get_mistake_book(book_name, str(PROGRESS_PATH))
            all_mistakes = mb.list_all(limit=10000)
            subjects = sorted({r.subject for r in all_mistakes if r.subject})
            subject_mistakes = [r for r in all_mistakes if not subject or r.subject == subject]
            mistake_stats = mb.get_stats(subject=subject or None)
            mistake_weak_points = mb.get_weak_points(subject=subject or None, top_n=10)
            due_mistakes = mb.get_due(subject=subject or None)
        except Exception:
            subjects = []
            subject_mistakes = []
            due_mistakes = []
            mistake_stats = {"total": 0, "due_today": 0, "by_type": {}, "by_tag": {}, "by_difficulty": {}}
            mistake_weak_points = []

        for item in recent_questions:
            question = item.get("question", "")
            if not question:
                continue
            for record in subject_mistakes:
                if question in "\\n".join([record.question_text, record.ocr_text, record.explanation]):
                    item["mistake_id"] = record.id
                    item["source"] = "mistake"
                    break
        if subject:
            recent_questions = [
                item for item in recent_questions
                if item.get("source") != "mistake" or item.get("mistake_id")
            ]

        def exposure_source(e: dict) -> str:
            return "mistake" if e.get("source") == "mistake" or e.get("intent") == "mistake" else "qa"

        def exposure_book(_: dict) -> str:
            return book_name or "未选择教材"

        daily_detail_map = defaultdict(lambda: {"qa": 0, "mistake": 0, "total": 0, "books": defaultdict(lambda: {"qa": 0, "mistake": 0, "total": 0, "concepts": Counter()})})
        for e in strict_exposures:
            day = (e.get("timestamp", "") or "")[:10] or "unknown"
            if day == "unknown":
                continue
            source = exposure_source(e)
            item_book = exposure_book(e)
            concept = str(e.get("concept") or "").strip()
            daily_item = daily_detail_map[day]
            daily_item[source] += 1
            daily_item["total"] += 1
            book_item = daily_item["books"][item_book]
            book_item[source] += 1
            book_item["total"] += 1
            if concept:
                book_item["concepts"][concept] += 1

        daily_details = []
        for day, item in sorted(daily_detail_map.items(), reverse=True)[:120]:
            subjects_detail = []
            for book_label, detail in sorted(item["books"].items(), key=lambda kv: kv[1]["total"], reverse=True):
                subjects_detail.append({
                    "subject": book_label,
                    "book_name": book_label,
                    "qa": detail["qa"],
                    "mistake": detail["mistake"],
                    "total": detail["total"],
                    "concepts": [
                        {"name": name, "count": count}
                        for name, count in detail["concepts"].most_common(8)
                    ],
                })
            daily_details.append({
                "date": day,
                "qa": item["qa"],
                "mistake": item["mistake"],
                "total": item["total"],
                "subjects": subjects_detail,
            })
        concept_review_plan = _build_concept_review_plan(
            book_name,
            concepts,
            strict_exposures,
            concept_counts,
            mistake_weak_points,
            subject=subject,
            limit=8,
        )
        return {
            "success": True,
            "data": {
                "stats": {
                    "total_concepts": len(strict_names),
                    "total_exposures": len(strict_exposures),
                    "weak_count": len(weak),
                    "forgotten_count": len([item for item in cm.get_forgotten(days_threshold=7, limit=100) if item.get("name") in strict_names]),
                    "frequent_top3": [
                        {"name": name, "exposure_count": count}
                        for name, count in concept_counts.most_common(3)
                    ],
                },
                "recent_exposures": recent_exposures,
                "recent_questions": recent_questions,
                "top_concepts": [
                    {"name": name, "count": count, **concepts.get(name, {})}
                    for name, count in concept_counts.most_common(12)
                ],
                "weak_concepts": weak[:12],
                "review_queue": review_queue,
                "concept_review_plan": concept_review_plan,
                "daily": [
                    {"date": day, **counts}
                    for day, counts in sorted(daily.items(), reverse=True)[:14]
                ],
                "daily_details": daily_details,
                "source_counts": dict(source_counts),
                "subjects": subjects,
                "selected_subject": subject,
                "review_rules": {
                    "mistake_due": "错题复习采用 SM-2：next_review 小于等于今天即进入待复习。评分 0-2 会重置间隔，3-5 会按掌握度拉长间隔。",
                    "concept_due": "概念复习按优先级推荐：薄弱标记、关联错题、7 天以上未接触或未复习、累计接触次数较高的概念会优先出现。",
                    "concept_reviewed": "点击已复习会写入 ConceptMemory 的 last_reviewed_at 与 review_history，并按质量更新 mastery_level/weak_flag。"
                },
                "due_mistakes": [_mistake_summary(r) for r in due_mistakes[:50]],
                "mistake_stats": mistake_stats,
                "mistake_weak_points": mistake_weak_points,
            },
        }
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


@router.post("/concept-review")
def mark_concept_review(payload: dict, book_name: str = ""):
    """Record that the user reviewed a concept from the Learning page."""
    if not book_name:
        return {"success": False, "message": "请先选择教材", "data": None}
    name = str(payload.get("name", "")).strip()
    if not name:
        return {"success": False, "message": "缺少概念名", "data": None}
    quality = int(payload.get("quality", 4) or 4)
    note = str(payload.get("note", ""))
    try:
        from knowledge.concept_memory import ConceptMemory
        updated = ConceptMemory(book_name).mark_reviewed(name, quality=quality, note=note)
        return {"success": True, "message": "已记录概念复习", "data": updated}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}

@router.get("/open-browser")
def open_kg_browser(book_name: str = ""):
    """在浏览器中打开图谱（仅本地有效）"""
    if not book_name:
        return {"success": False, "message": "请先选择教材"}
    html_path = _kg_html_path(book_name)
    if not html_path.exists():
        return {"success": False, "message": "知识图谱未生成，请先刷新"}
    import webbrowser
    webbrowser.open(html_path.as_uri())
    return {"success": True, "message": f"已在浏览器打开: {html_path.name}"}
