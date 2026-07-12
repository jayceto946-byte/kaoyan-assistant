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

def test_exercise_subject_hierarchy_filters_and_stats(tmp_path):
    bank = ExerciseBank(tmp_path / "exercises.db")
    high_math = ExerciseRecord(question_text="q1", subject="\u6570\u5b66/\u9ad8\u6570", status="new")
    linear = ExerciseRecord(question_text="q2", subject="\u6570\u5b66/\u7ebf\u4ee3", status="needs_review")
    english = ExerciseRecord(question_text="q3", subject="\u82f1\u8bed/\u9605\u8bfb", status="new")
    for record in [high_math, linear, english]:
        bank.add(record)

    assert {r.id for r in bank.list_all(subject="\u6570\u5b66")} == {high_math.id, linear.id}
    assert {r.id for r in bank.list_all(subject="\u6570\u5b66/\u9ad8\u6570")} == {high_math.id}
    stats = bank.stats(subject="\u6570\u5b66")
    assert stats["total"] == 2
    assert stats["by_status"]["needs_review"] == 1


def test_exercise_answer_job_runs_after_request_returns(monkeypatch, tmp_path):
    import time
    from backend.job_manager import JobManager
    from backend.schemas import ExerciseAnswerGenerateRequest

    bank = ExerciseBank(tmp_path / "answer_jobs_exercises.db")
    exercise_id = bank.add(ExerciseRecord(question_text="解释霍尔效应", subject="专业课/传感器"))
    jobs = JobManager(tmp_path / "answer_jobs.sqlite3")
    monkeypatch.setattr(exercises, "_bank", lambda book_name="default": bank)
    monkeypatch.setattr(exercises, "get_job_manager", lambda: jobs)
    monkeypatch.setattr(
        exercises,
        "generate_exercise_answer",
        lambda req, book_name="default": {
            "success": True,
            "message": "draft ready",
            "data": {"answer": "教材答案", "evidence_count": 2},
        },
    )

    created = exercises.create_exercise_answer_job(
        ExerciseAnswerGenerateRequest(id=exercise_id),
        book_name="传感器短书",
    )
    assert created["success"] is True
    job_id = created["job_id"]

    deadline = time.time() + 3
    job = jobs.get_job(job_id)
    while job and job["status"] not in {"completed", "failed"} and time.time() < deadline:
        time.sleep(0.02)
        job = jobs.get_job(job_id)

    assert job is not None
    assert job["status"] == "completed"
    assert job["result"]["answer"] == "教材答案"
    assert exercises.latest_exercise_answer_job(exercise_id, "传感器短书")["data"]["id"] == job_id
