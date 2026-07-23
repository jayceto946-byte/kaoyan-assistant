from collections import Counter
from datetime import datetime, timedelta
from types import SimpleNamespace

from backend.services.kg_learning_summary import (
    build_concept_review_plan,
    days_since,
    mistake_summary,
)


def _mistake(**updates):
    values = {
        "id": "m-1",
        "question_text": "请说明牛顿第二定律",
        "ocr_text": "",
        "explanation": "",
        "source": "manual",
        "subject": "物理",
        "chapter": "力学",
        "tags": ["动力学"],
        "mistake_type": "概念不清",
        "review_history": [],
        "linked_concepts": [{"name": "牛顿第二定律"}],
        "sm2": {"next_review": "2026-07-24", "interval": 2},
    }
    values.update(updates)
    return SimpleNamespace(**values)


def test_days_since_uses_supplied_reference_time():
    reference = datetime(2026, 7, 23, 12, 0, 0)
    assert days_since("2026-07-13T11:00:00", now=reference) == 10
    assert days_since("not-a-date", now=reference) is None


def test_review_plan_is_calculated_from_preloaded_records():
    reference = datetime(2026, 7, 23, 12, 0, 0)
    concepts = {
        "牛顿第二定律": {
            "weak_flag": True,
            "exposure_count": 3,
            "last_exposed_at": (reference - timedelta(days=10)).isoformat(),
            "source_chapters": ["第二章"],
        }
    }
    exposures = [{
        "concept": "牛顿第二定律",
        "question": "请说明牛顿第二定律",
        "source": "mistake",
        "timestamp": "2026-07-12T08:00:00",
        "weak": True,
    }]

    result = build_concept_review_plan(
        concepts,
        exposures,
        Counter({"牛顿第二定律": 3}),
        [],
        [_mistake()],
        now=reference,
    )

    assert len(result) == 1
    assert result[0]["name"] == "牛顿第二定律"
    assert result[0]["related_mistakes"][0]["id"] == "m-1"
    assert result[0]["recent_questions"][0]["mistake_id"] == "m-1"
    assert result[0]["textbook_snippets"][0]["chapter"] == "第二章"


def test_mistake_summary_keeps_existing_response_shape():
    summary = mistake_summary(_mistake())
    assert summary["next_review"] == "2026-07-24"
    assert summary["interval"] == 2
    assert summary["linked_concepts"] == [{"name": "牛顿第二定律"}]
