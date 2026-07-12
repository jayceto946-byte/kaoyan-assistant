import json

from fastapi.testclient import TestClient

from backend.main import app
from memory.textbook_exercise_importer import extract_textbook_exercise_text


def test_extract_textbook_exercises_from_source_package(tmp_path, monkeypatch):
    progress = tmp_path / "progress"
    book_dir = progress / "demo"
    source_dir = book_dir / "chapter_highlights" / "chapter_001"
    source_dir.mkdir(parents=True)
    (book_dir / "_chapters.json").write_text(
        json.dumps([{"title": "第一章 测试", "page_number": 10, "end_page": 12}], ensure_ascii=False),
        encoding="utf-8",
    )
    (source_dir / "source_package.json").write_text(
        json.dumps(
            {
                "book_name": "demo",
                "chapter": {"title": "第一章 测试"},
                "practice_sections": [
                    {
                        "title": "习题",
                        "chunks": [
                            {"text": "1. 求函数 f(x)=x^2 的导数。", "page": 11, "chunk_id": "c1", "role": "exercise"},
                            {"text": "2. 证明极小值条件。", "page": 12, "chunk_id": "c2", "role": "exercise"},
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("memory.textbook_exercise_importer.PROGRESS_PATH", progress)

    extracted = extract_textbook_exercise_text("demo", chapter="第一章", page_start=11, page_end=11)

    assert extracted.provider == "chapter-highlight-source-package"
    assert "求函数" in extracted.text
    assert "证明极小值" not in extracted.text
    assert extracted.chunk_count == 1


def test_textbook_analyze_api(monkeypatch, tmp_path):
    progress = tmp_path / "progress"
    book_dir = progress / "demo"
    source_dir = book_dir / "chapter_highlights" / "chapter_001"
    source_dir.mkdir(parents=True)
    (source_dir / "source_package.json").write_text(
        json.dumps(
            {
                "book_name": "demo",
                "chapter": {"title": "第一章"},
                "practice_sections": [
                    {
                        "title": "习题",
                        "chunks": [
                            {"text": "1. 求线性规划最优解。\n2. 判断矩阵是否可逆。", "page": 3, "chunk_id": "c1", "role": "exercise"}
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("memory.textbook_exercise_importer.PROGRESS_PATH", progress)

    client = TestClient(app)
    res = client.post("/api/exercises/textbook-analyze", json={"book_name": "demo", "subject": "专业课"}).json()

    assert res["success"] is True
    assert res["summary"]["total"] == 2
    assert res["extract"]["provider"] == "chapter-highlight-source-package"


def test_explicit_page_range_excludes_chunks_without_page_metadata(tmp_path, monkeypatch):
    progress = tmp_path / "progress"
    source_dir = progress / "demo" / "chapter_highlights" / "chapter_001"
    source_dir.mkdir(parents=True)
    (source_dir / "source_package.json").write_text(
        json.dumps(
            {
                "book_name": "demo",
                "chapter": {"title": "Chapter"},
                "practice_sections": [
                    {
                        "title": "Exercises",
                        "chunks": [
                            {"text": "1. Unknown page question", "role": "exercise"},
                            {"text": "2. Selected page question", "page": 8, "role": "exercise"},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("memory.textbook_exercise_importer.PROGRESS_PATH", progress)

    extracted = extract_textbook_exercise_text("demo", page_start=8, page_end=8)

    assert "Selected page question" in extracted.text
    assert "Unknown page question" not in extracted.text
    assert extracted.chunk_count == 1


def test_page_metadata_supports_zero_based_index_and_source_markdown():
    from memory.textbook_exercise_importer import _page_from_item

    assert _page_from_item({"page_idx": 0}) == 1
    assert _page_from_item({"source_markdown": "CGQ_118.md"}) == 118
