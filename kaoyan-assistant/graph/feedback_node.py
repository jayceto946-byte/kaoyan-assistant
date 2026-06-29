"""反馈节点 — 更新记忆 + 掌握度 + 优化策略"""
from memory.study_memory import StudyMemory
from memory.spaced_repetition import SpacedRepetition


def feedback_node(state: dict) -> dict:
    """收集用户反馈并更新学习状态"""
    book_name = state.get("book_name", "default")
    target_chapters = state.get("target_chapters", [])
    feedback = state.get("user_feedback") or {}

    memory = StudyMemory(book_name)
    sr = SpacedRepetition(book_name)

    mastery_update = {}

    # 更新章节学习标记
    for ch in target_chapters:
        memory.mark_chapter_studied(ch)
        mastery_update[ch] = memory.get_chapter_progress(ch)

    # 处理反馈评分
    rating = feedback.get("rating", 0)
    if rating and target_chapters:
        ch = target_chapters[0]
        kp = feedback.get("knowledge_point", f"{ch}_auto")
        card_id = f"{ch}::{kp}"
        sr.add_knowledge_point(card_id, ch, kp)
        quality = _rating_to_quality(rating)
        sr.review(card_id, quality)

    # 如果做了题，更新 SR
    quiz_questions = state.get("quiz_questions", [])
    for q in quiz_questions:
        if isinstance(q, dict) and not q.get("error"):
            kp = q.get("knowledge_point", q.get("question", "")[:30])
            card_id = f"{target_chapters[0] if target_chapters else 'general'}::{kp}"
            sr.add_knowledge_point(card_id, target_chapters[0] if target_chapters else "", kp)

    linked_concepts = _record_concept_memory(state)

    return {
        "mastery_update": mastery_update,
        "user_feedback": None,
        "linked_concepts": linked_concepts,
    }


_GENERIC_ALIAS_TERMS = {
    "\u65b9\u6cd5", "\u6b65\u9aa4", "\u8fed\u4ee3", "\u8fed\u4ee3\u6b65\u9aa4", "\u7a0b\u5e8f\u6846\u56fe", "\u539f\u7406", "\u8fc7\u7a0b", "\u7b97\u6cd5", "\u7ea6\u675f", "\u4f18\u5316", "\u4f18\u5316\u65b9\u6cd5", "\u6700\u4f18\u5316\u65b9\u6cd5", "\u95ee\u9898", "\u6761\u4ef6",
    "method", "step", "steps", "algorithm",
}


def _strict_concepts(concepts: list[dict], question: str = "") -> list[dict]:
    strict = []
    question_text = (question or "").lower()
    for concept in concepts:
        try:
            if float(concept.get("confidence", 0) or 0) < 0.999:
                continue
        except (TypeError, ValueError):
            continue

        name = str(concept.get("name", "")).strip()
        aliases = [str(a).strip() for a in concept.get("aliases", []) if str(a).strip()]
        direct_terms = [name, *[a for a in aliases if a not in _GENERIC_ALIAS_TERMS]]
        if question_text and not any(term and term.lower() in question_text for term in direct_terms):
            continue
        strict.append(concept)
    return strict


def _record_concept_memory(state: dict) -> list[dict]:
    """Link final QA output to KG concepts and persist shared concept memory."""
    try:
        from knowledge.concept_linker import ConceptLinker, is_unclear_intent
        from knowledge.concept_memory import ConceptMemory

        book_name = state.get("book_name", "default")
        intent = state.get("intent", "qa")
        chapter_contents = state.get("chapter_contents", {}) or {}
        chunks = []
        for docs in chapter_contents.values():
            chunks.extend(docs[:2])

        linker = ConceptLinker(book_name)
        concepts = linker.link(
            question=state.get("user_input", ""),
            answer=state.get("final_output", ""),
            chunks=chunks,
            matched_concepts=state.get("matched_concepts", []),
            intent=intent,
            limit=8,
        )
        concepts = _strict_concepts(concepts, state.get("user_input", ""))
        if not concepts:
            return []

        memory = ConceptMemory(book_name)
        memory.log_exposure(
            concepts,
            state.get("user_input", ""),
            intent,
            source="qa",
            weak=is_unclear_intent(intent),
        )
        return concepts
    except Exception as e:
        print(f"[ConceptMemory] QA record failed: {e}", flush=True)
        return []

def _rating_to_quality(rating) -> int:
    if isinstance(rating, (int, float)):
        r = float(rating)
        if r >= 5:
            return 5
        elif r >= 4:
            return 4
        elif r >= 3:
            return 3
        elif r >= 2:
            return 2
        elif r >= 1:
            return 1
    return 3
