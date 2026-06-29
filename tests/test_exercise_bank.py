from fastapi.testclient import TestClient

from backend.api import exercises
from backend.main import app
from memory.exercise_bank import ExerciseBank, ExerciseRecord
from memory.mistake_book import MistakeBook, MistakeRecord


def test_exercise_bank_crud_practice_and_stats(tmp_path):
    bank = ExerciseBank(tmp_path / "exercises.db")
    rid = bank.add(
        ExerciseRecord(
            question_text="求导 $x^2$",
            answer="$2x$",
            explanation="幂函数求导",
            subject="数学",
            tags=["导数"],
            question_type="计算题",
            status="new",
        )
    )

    loaded = bank.get(rid)
    assert loaded is not None
    assert loaded.question_text == "求导 $x^2$"
    assert bank.list_all(tag="导数")[0].id == rid

    practiced = bank.record_practice(rid, user_answer="$2x$", quality=5)
    assert practiced is not None
    assert practiced.status == "mastered"
    assert practiced.practice_count == 1
    assert practiced.practice_history[0]["user_answer"] == "$2x$"
    assert bank.stats()["by_status"]["mastered"] == 1


def test_exercises_api_add_list_status_practice_and_import_mistake(monkeypatch, tmp_path):
    bank = ExerciseBank(tmp_path / "api_exercises.db")
    mistake_book = MistakeBook(tmp_path / "mistakes.db")
    mistake_id = mistake_book.add(
        MistakeRecord(
            question_text="错题：求 $x^2$ 的导数",
            correct_answer="$2x$",
            explanation="使用幂函数求导公式。",
            subject="数学",
            tags=["导数"],
            mistake_type=["计算错误"],
        )
    )

    monkeypatch.setattr(exercises, "_bank", lambda book_name="default": bank)
    monkeypatch.setattr(exercises, "get_mistake_book", lambda book_name="default", data_dir="": mistake_book)
    client = TestClient(app)

    add_res = client.post(
        "/api/exercises/add",
        json={
            "question_text": "手工题：求极限",
            "answer": "1",
            "subject": "数学",
            "tags": "极限",
            "question_type": "填空题",
        },
    ).json()
    assert add_res["success"] is True
    exercise_id = add_res["id"]

    list_res = client.post("/api/exercises/list", json={"search_kw": "极限"}).json()
    assert list_res["success"] is True
    assert list_res["data"][0]["id"] == exercise_id

    status_res = client.post("/api/exercises/status", json={"id": exercise_id, "status": "mastered"}).json()
    assert status_res["success"] is True
    assert status_res["data"]["status"] == "mastered"

    practice_res = client.post(
        "/api/exercises/practice",
        json={"id": exercise_id, "user_answer": "不会", "quality": 1, "add_to_mistake": True},
    ).json()
    assert practice_res["success"] is True
    assert practice_res["data"]["status"] == "needs_review"
    assert practice_res["data"]["practice_count"] == 1
    assert practice_res["mistake_id"]
    assert mistake_book.get(practice_res["mistake_id"]).user_answer == "不会"

    to_mistake_res = client.post(
        "/api/exercises/to-mistake",
        json={"id": exercise_id, "user_answer": "还是不会", "mistake_type": ["概念不清"]},
    ).json()
    assert to_mistake_res["success"] is True
    assert to_mistake_res["id"]

    import_res = client.post("/api/exercises/from-mistake", json={"mistake_id": mistake_id}).json()
    assert import_res["success"] is True
    assert import_res["data"]["origin_type"] == "mistake"
    assert import_res["data"]["origin_id"] == mistake_id

    duplicate_res = client.post("/api/exercises/from-mistake", json={"mistake_id": mistake_id}).json()
    assert duplicate_res["success"] is True
    assert duplicate_res["id"] == import_res["id"]