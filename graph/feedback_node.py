"""反馈节点 — 更新记忆 + 掌握度 + 优化策略"""
from memory.study_memory import StudyMemory
from memory.spaced_repetition import SpacedRepetition


def _feedback_node_impl(state: dict) -> dict:
    """Collect feedback and update learning state."""
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


def feedback_node(state: dict) -> dict:
    """Best-effort feedback that never invalidates an already generated answer."""
    try:
        return _feedback_node_impl(state)
    except Exception as exc:
        print(f"[feedback] record failed: {exc}", flush=True)
        return {
            "mastery_update": {},
            "user_feedback": None,
            "linked_concepts": link_concepts_for_response(state),
        }

def link_concepts_for_response(state: dict) -> list[dict]:
    """Resolve UI concept links locally without writing data or calling an LLM."""
    try:
        raw_concepts = _link_concepts_locally(state)
        return _strict_concepts(raw_concepts, str(state.get("user_input", "")))
    except Exception as exc:
        print(f"[ConceptMemory] response linking failed: {exc}", flush=True)
        return []


_GENERIC_ALIAS_TERMS = {
    "\u65b9\u6cd5", "\u6b65\u9aa4", "\u8fed\u4ee3", "\u8fed\u4ee3\u6b65\u9aa4", "\u7a0b\u5e8f\u6846\u56fe", "\u539f\u7406", "\u8fc7\u7a0b", "\u7b97\u6cd5", "\u7ea6\u675f", "\u4f18\u5316", "\u4f18\u5316\u65b9\u6cd5", "\u6700\u4f18\u5316\u65b9\u6cd5", "\u95ee\u9898", "\u6761\u4ef6",
    "method", "step", "steps", "algorithm",
}


def _strict_concepts(concepts: list[dict], question: str = "") -> list[dict]:
    strict = []
    question_text = (question or "").lower()
    for concept in concepts:
        try:
            if float(concept.get("confidence", 0) or 0) < 0.85:
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
        from knowledge.concept_linker import is_unclear_intent
        from knowledge.concept_memory import ConceptMemory
        from memory.learning_events import LearningEvent, concept_names, get_learning_event_store

        book_name = state.get("book_name", "default")
        intent = state.get("intent", "qa")
        subject = state.get("subject", "")
        conversation_id = state.get("conversation_id", "")
        question = state.get("user_input", "")
        answer = state.get("final_output", "")
        raw_concepts = _link_concepts_locally(state)

        memory = ConceptMemory(book_name)
        concepts = _strict_concepts(raw_concepts, question)
        if concepts:
            memory.log_exposure(
                concepts,
                question,
                intent,
                source="qa",
                weak=is_unclear_intent(intent),
                subject=subject,
                conversation_id=conversation_id,
            )

        candidates = [item for item in raw_concepts if item not in concepts]
        if candidates:
            memory.log_candidates(
                candidates,
                question,
                intent,
                source="qa_linker_candidate" if raw_concepts else "qa_llm_candidate",
                subject=subject,
                conversation_id=conversation_id,
                answer=answer,
            )

        store = get_learning_event_store()
        store.append(LearningEvent(
            event_type="chat_qa",
            book_name=book_name,
            subject=subject,
            conversation_id=conversation_id,
            source_type="conversation",
            source_id=conversation_id,
            concept_names=concept_names(concepts),
            payload={
                "intent": intent,
                "question": question[:300],
                "answer_preview": answer[:500],
                "target_chapters": state.get("target_chapters", []),
                "retrieval_status": state.get("retrieval_status", ""),
                "candidate_count": len(candidates or []),
            },
        ))
        for item in concepts:
            store.append(LearningEvent(
                event_type="concept_exposure",
                book_name=book_name,
                subject=subject,
                conversation_id=conversation_id,
                source_type="conversation",
                source_id=conversation_id,
                concept_names=concept_names([item]),
                payload={
                    "intent": intent,
                    "question": question[:300],
                    "confidence": item.get("confidence", 0),
                    "link_source": item.get("source", ""),
                    "weak": is_unclear_intent(intent),
                },
            ))
        if candidates:
            store.append(LearningEvent(
                event_type="concept_candidates",
                book_name=book_name,
                subject=subject,
                conversation_id=conversation_id,
                source_type="conversation",
                source_id=conversation_id,
                concept_names=concept_names(candidates),
                payload={
                    "intent": intent,
                    "question": question[:300],
                    "candidate_count": len(candidates),
                },
            ))

        return concepts
    except Exception as e:
        print(f"[ConceptMemory] QA record failed: {e}", flush=True)
        return []


def _link_concepts_locally(state: dict) -> list[dict]:
    """Use only the local KG linker; automatic feedback must never add an LLM call."""
    from knowledge.concept_linker import ConceptLinker

    chapter_contents = state.get("chapter_contents", {}) or {}
    chunks: list[str] = []
    for docs in chapter_contents.values():
        chunks.extend(docs[:2])

    return ConceptLinker(state.get("book_name", "default")).link(
        question=state.get("user_input", ""),
        answer=state.get("final_output", ""),
        chunks=chunks,
        matched_concepts=state.get("matched_concepts", []),
        intent=state.get("intent", "qa"),
        limit=8,
    )


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
