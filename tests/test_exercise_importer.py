from fastapi.testclient import TestClient

from backend.api import exercises
from backend.main import app
from memory.exercise_bank import ExerciseBank, ExerciseRecord
from memory.exercise_file_importer import ExtractedExerciseText
from memory.exercise_importer import analyze_candidate, attach_answers_by_number, split_candidate_text


def test_split_and_analyze_candidates_without_llm():
    raw = """
1. 求函数 f(x)=x^2 的导数。
A. x B. 2x C. x^2 D. 1

2. 简述线性规划中可行域和最优解的关系。
"""
    chunks = split_candidate_text(raw)
    assert len(chunks) == 2

    first = analyze_candidate(chunks[0], subject="数学")
    assert first.suggested_type == "选择题"
    assert "导数" in first.tags
    assert first.confidence >= 0.6

    second = analyze_candidate(chunks[1], subject="优化设计")
    assert second.suggested_type == "简答题"
    assert "线性规划" in second.tags


def test_exercises_api_analyze_and_batch_add(monkeypatch, tmp_path):
    bank = ExerciseBank(tmp_path / "api_exercises.db")
    monkeypatch.setattr(exercises, "_bank", lambda book_name="default": bank)
    client = TestClient(app)

    analyze_res = client.post(
        "/api/exercises/analyze-candidates?book_name=优化设计",
        json={
            "raw_text": "1. 计算线性规划问题的最优解。\n\n2. 判断：矩阵 A 可逆当且仅当行列式不为 0。",
            "source": "导入测试",
            "subject": "优化设计",
        },
    ).json()
    assert analyze_res["success"] is True
    assert analyze_res["summary"]["total"] == 2
    candidates = analyze_res["data"]
    assert candidates[0]["suggested_type"] == "计算题"

    batch_res = client.post(
        "/api/exercises/batch-add?book_name=优化设计",
        json={
            "exercises": [
                {
                    "question_text": item["question_text"],
                    "source": item["source"],
                    "subject": item["subject"],
                    "chapter": item["chapter"],
                    "tags": ", ".join(item["tags"]),
                    "question_type": item["suggested_type"],
                    "difficulty": item["difficulty"],
                    "linked_concepts": item["linked_concepts"],
                    "origin_type": "import_candidate",
                    "origin_id": item["id"],
                    "status": "needs_review",
                    "notes": "; ".join(item["reasons"]),
                }
                for item in candidates
            ]
        },
    ).json()
    assert batch_res["success"] is True
    assert batch_res["count"] == 2
    assert bank.stats()["total"] == 2

def test_analyze_marks_existing_duplicate_and_validation_issues(monkeypatch, tmp_path):
    bank = ExerciseBank(tmp_path / "duplicate_exercises.db")
    existing_text = "1. 计算线性规划问题的最优解。"
    existing_id = bank.add(ExerciseRecord(question_text=existing_text, subject="优化设计"))
    monkeypatch.setattr(exercises, "_bank", lambda book_name="default": bank)
    client = TestClient(app)

    response = client.post(
        "/api/exercises/analyze-candidates?book_name=优化设计",
        json={"raw_text": existing_text, "subject": "优化设计"},
    ).json()

    assert response["success"] is True
    assert response["data"][0]["duplicate_of"] == existing_id
    assert "与题库现有题目重复" in response["data"][0]["validation_issues"]


def test_attach_separate_answer_sheet_by_explicit_question_number():
    candidates = [
        analyze_candidate("1. 选择正确答案。A. 1 B. 2 C. 3 D. 4"),
        analyze_candidate("2. 计算函数 x^2 的导数。"),
        analyze_candidate("3. 说明拉格朗日乘子法。"),
    ]

    paired = attach_answers_by_number(candidates, "1. 答案：B\n2. $2x$")

    assert paired == 2
    assert candidates[0].answer == "B"
    assert candidates[1].answer == "$2x$"
    assert "答案文件中未找到匹配答案" in candidates[2].validation_issues


def test_upload_analyze_accepts_separate_answer_file(monkeypatch, tmp_path):
    bank = ExerciseBank(tmp_path / "paired_upload.db")
    monkeypatch.setattr(exercises, "_bank", lambda book_name="default": bank)
    monkeypatch.setattr(exercises, "_save_upload", lambda upload: tmp_path / str(upload.filename))

    def fake_extract(path):
        if "answer" in path.name:
            return ExtractedExerciseText(text="1. B\n2. $2x$", file_type="docx")
        return ExtractedExerciseText(
            text="1. 选择正确答案。A. 1 B. 2 C. 3 D. 4\n\n2. 计算函数 x^2 的导数。",
            file_type="docx",
        )

    monkeypatch.setattr(exercises, "extract_exercise_text", fake_extract)
    client = TestClient(app)
    response = client.post(
        "/api/exercises/upload-analyze",
        files={
            "file": ("questions.docx", b"questions", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "answer_file": ("answers.docx", b"answers", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        },
        data={"subject": "数学"},
    ).json()

    assert response["success"] is True
    assert response["summary"]["paired_answers"] == 2
    assert [item["answer"] for item in response["data"]] == ["B", "$2x$"]
