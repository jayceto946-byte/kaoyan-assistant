from fastapi.testclient import TestClient

from backend.api import exercises
from backend.main import app
from memory.exercise_bank import ExerciseBank
from memory.exercise_importer import analyze_candidate, split_candidate_text


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