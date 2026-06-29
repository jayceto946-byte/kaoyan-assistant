from fastapi.testclient import TestClient

from backend.main import app
from backend.api import mistakes
from memory.mistake_book import MistakeBook


def test_mistakes_api_add_persists_explanation(monkeypatch, tmp_path):
    book = MistakeBook(tmp_path / "api_mistakes.db")
    monkeypatch.setattr(mistakes, "_mb", lambda book_name="default": book)

    def fake_concepts(record, explanation="", book_name="default"):
        record.linked_concepts = [{"name": "limit", "concept_id": "c-limit", "confidence": 1.0, "source": "mistake_llm"}]
        return record.linked_concepts

    monkeypatch.setattr(mistakes, "_persist_mistake_concepts", fake_concepts)
    client = TestClient(app)

    payload = {
        "question_text": "题干 $x$",
        "subject": "数学",
        "tags": "极限",
        "mistake_type": ["概念不清"],
        "difficulty": 4,
        "ocr_text": "OCR 题干",
        "explanation": "保存的解答 $x+1$",
    }
    add_res = client.post("/api/mistakes/add", json=payload).json()
    assert add_res["success"] is True
    assert add_res["data"]["explanation"] == "保存的解答 $x+1$"

    list_res = client.post("/api/mistakes/list", json={"limit": 10}).json()
    assert list_res["success"] is True
    assert list_res["data"][0]["explanation"] == "保存的解答 $x+1$"
