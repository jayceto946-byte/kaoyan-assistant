from fastapi.testclient import TestClient

from backend.api import exercises, mistakes
from backend.main import app
from memory.exercise_bank import ExerciseBank, ExerciseRecord
from memory.mistake_book import MistakeBook, MistakeRecord


def test_exercise_overview_combines_records_stats_and_active_session(tmp_path, monkeypatch):
    bank = ExerciseBank(tmp_path / "exercises.db")
    record = ExerciseRecord(question_text="聚合接口习题", subject="数学")
    bank.add(record)
    session = bank.create_practice_session(subject="数学", limit=1)
    monkeypatch.setattr(exercises, "_bank", lambda book_name="default": bank)

    response = TestClient(app).post(
        "/api/exercises/overview",
        json={"subject": "数学", "limit": 100},
    ).json()

    assert response["success"] is True
    assert response["data"]["records"][0]["id"] == record.id
    assert response["data"]["stats"]["total"] == 1
    assert response["data"]["practice_session"]["id"] == session.id


def test_mistake_overview_combines_records_and_due_queue(tmp_path, monkeypatch):
    book = MistakeBook(tmp_path / "mistakes.db")
    record = MistakeRecord(question_text="聚合接口错题", subject="数学")
    book.add(record)
    monkeypatch.setattr(mistakes, "_mb", lambda book_name="default": book)

    response = TestClient(app).post(
        "/api/mistakes/overview",
        json={"subject": "数学", "limit": 50},
    ).json()

    assert response["success"] is True
    assert response["data"]["records"][0]["id"] == record.id
    assert isinstance(response["data"]["due_records"], list)
