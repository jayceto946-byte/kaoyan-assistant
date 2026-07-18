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

    refreshed = client.get(f"/api/kg/learning-summary?book_name={book_name}").json()
    assert all(item["name"] != "导数" for item in refreshed["data"]["concept_review_plan"])
    assert all(item["name"] != "导数" for item in refreshed["data"]["review_queue"])


def test_definition_question_is_strict_but_not_automatically_weak(monkeypatch, tmp_path):
    book_name = "definition-book"
    progress_root = tmp_path / "progress"

    import config
    import backend.api.kg as kg_api
    import knowledge.concept_memory as concept_memory_module

    monkeypatch.setattr(config, "PROGRESS_PATH", progress_root)
    monkeypatch.setattr(kg_api, "PROGRESS_PATH", progress_root)
    monkeypatch.setattr(concept_memory_module, "PROGRESS_PATH", progress_root)

    cm = ConceptMemory(book_name)
    cm.log_exposure(
        [{"name": "压阻效应", "confidence": 0.88}],
        "什么是压阻效应",
        "definition",
        source="qa",
        weak=True,
    )

    summary = TestClient(app).get(f"/api/kg/learning-summary?book_name={book_name}").json()["data"]
    assert summary["stats"]["total_concepts"] == 1
    assert summary["stats"]["total_exposures"] == 1
    assert summary["stats"]["weak_count"] == 0
    assert summary["concept_review_plan"][0]["weak"] is False

def test_generic_learning_summary_keeps_concepts_and_question_stems(monkeypatch, tmp_path):
    progress_root = tmp_path / "progress"

    import config
    import backend.api.kg as kg_api
    import knowledge.concept_memory as concept_memory_module
    import memory.learning_events as learning_events
    from memory.learning_events import LearningEvent, LearningEventStore

    monkeypatch.setattr(config, "PROGRESS_PATH", progress_root)
    monkeypatch.setattr(kg_api, "PROGRESS_PATH", progress_root)
    monkeypatch.setattr(concept_memory_module, "PROGRESS_PATH", progress_root)

    event_store = LearningEventStore(progress_root / "learning_events.db")
    monkeypatch.setattr(learning_events, "get_learning_event_store", lambda: event_store)

    cm = ConceptMemory("default")
    cm.log_exposure(
        [{"name": "主旨句", "confidence": 0.95, "aliases": []}],
        "主旨句通常怎么定位",
        "qa",
        source="qa",
        subject="英语/阅读",
        conversation_id="conv-generic",
    )
    event_store.append(
        LearningEvent(
            event_type="chat_qa",
            book_name="default",
            subject="英语/阅读",
            conversation_id="conv-generic",
            concept_names=["主旨句"],
            payload={"intent": "qa", "question": "主旨句通常怎么定位"},
        )
    )
    event_store.append(
        LearningEvent(
            event_type="chat_qa",
            book_name="default",
            subject="英语/阅读",
            conversation_id="conv-question-only",
            payload={"intent": "qa", "question": "这道阅读题为什么选 B"},
        )
    )

    client = TestClient(app)
    response = client.get("/api/kg/learning-summary", params={"subject": "英语/阅读"}).json()

    assert response["success"] is True
    summary = response["data"]
    assert summary["stats"]["total_concepts"] == 1
    assert summary["top_concepts"][0]["name"] == "主旨句"
    assert {item["question"] for item in summary["recent_questions"]} == {
        "主旨句通常怎么定位",
        "这道阅读题为什么选 B",
    }
    assert "英语/阅读" in summary["subjects"]

    review = client.post("/api/kg/concept-review", json={"name": "主旨句", "quality": 4}).json()
    assert review["success"] is True
