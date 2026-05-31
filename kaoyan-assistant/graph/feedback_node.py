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

    return {
        "mastery_update": mastery_update,
        "user_feedback": None,
    }


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
