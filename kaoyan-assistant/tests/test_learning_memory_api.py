from fastapi.testclient import TestClient

from backend.main import app
from knowledge.concept_memory import ConceptMemory
from memory.mistake_book import MistakeBook, MistakeRecord


def test_learning_summary_returns_actionable_concept_review_plan(monkeypatch, tmp_path):
    book_name = "review-book"
    progress_root = tmp_path / "progress"

    import config
    import backend.api.kg as kg_api
    import knowledge.concept_memory as concept_memory_module

    monkeypatch.setattr(config, "PROGRESS_PATH", progress_root)
    monkeypatch.setattr(kg_api, "PROGRESS_PATH", progress_root)
    monkeypatch.setattr(concept_memory_module, "PROGRESS_PATH", progress_root)

    cm = ConceptMemory(book_name)
    cm.log_exposure(
        [
            {
                "name": "导数",
                "confidence": 1.0,
                "definition": "导数描述函数在一点处的变化率。",
                "source_chapters": ["第一章 函数与导数"],
            }
        ],
        "导数怎么复习",
        "qa",
        source="qa",
        weak=True,
    )

    mb = MistakeBook(progress_root / f"mistake_book_{book_name}.db")
    mb.add(
        MistakeRecord(
            question_text="求 $x^2$ 的导数",
            subject="数学",
            tags=["导数"],
            mistake_type=["计算错误"],
            explanation="使用幂函数求导公式。",
        )
    )

    client = TestClient(app)
    summary = client.get(f"/api/kg/learning-summary?book_name={book_name}").json()

    assert summary["success"] is True
    plan = summary["data"]["concept_review_plan"]
    assert plan
    card = plan[0]
    assert card["name"] == "导数"
    assert card["reasons"]
    assert card["related_mistakes"]
    assert card["textbook_snippets"]
    assert card["recent_questions"][0]["question"] == "导数怎么复习"

    review = client.post(f"/api/kg/concept-review?book_name={book_name}", json={"name": "导数", "quality": 4}).json()

    assert review["success"] is True
    reloaded = ConceptMemory(book_name)
    assert reloaded._data["concepts"]["导数"]["review_count"] == 1
    assert reloaded._data["concepts"]["导数"]["last_review_quality"] == 4
