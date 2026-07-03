import json

import pytest

from backend.job_manager import JobCancelled, JobManager
from ingestion.chunk_roles import assign_chunk_roles, classify_chunk_role


def test_job_manager_lifecycle_and_restart_recovery(tmp_path):
    manager = JobManager(tmp_path / "jobs.sqlite3")
    job = manager.create_job(
        "textbook_import",
        {"book_name": "linear_algebra", "file_path": "book.pdf"},
        status="running",
        message="queued",
    )

    assert job["book_name"] == "linear_algebra"
    updated = manager.update_job(job["id"], stage="indexing", progress=42, message="working")
    assert updated["progress"] == 42
    assert updated["stage"] == "indexing"

    cancelling = manager.request_cancel(job["id"])
    assert cancelling["status"] == "cancelling"
    with pytest.raises(JobCancelled):
        manager.raise_if_cancelled(job["id"])

    manager.update_job(job["id"], status="cancelled", stage="cancelled", progress=100)
    assert manager.mark_running_interrupted() == 0

    running = manager.create_job("chapter_highlight", {"chapter_id": "c1"}, status="running")
    assert manager.mark_running_interrupted() == 1
    assert manager.get_job(running["id"])["status"] == "interrupted"


def test_job_manager_imports_legacy_json_jobs(tmp_path):
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    (legacy_dir / "abc.json").write_text(
        json.dumps(
            {
                "id": "abc",
                "status": "completed",
                "stage": "completed",
                "progress": 100,
                "message": "done",
                "book_name": "math",
                "result": {"indexed_chunks": 3},
                "created_at": "2026-01-01T00:00:00",
                "updated_at": "2026-01-01T00:01:00",
            }
        ),
        encoding="utf-8",
    )

    manager = JobManager(tmp_path / "jobs.sqlite3")
    assert manager.import_legacy_json_jobs("textbook_import", legacy_dir, input_keys=("book_name",)) == 1
    imported = manager.get_job("abc")
    assert imported["book_name"] == "math"
    assert imported["result"] == {"indexed_chunks": 3}


def test_chunk_role_classifier_and_kg_precedence():
    chunks = [
        {"chunk_id": "d1", "content": "定义 设 V 是向量空间，称满足条件的映射为线性变换。"},
        {"chunk_id": "e1", "content": "例题 计算矩阵 A 的特征值。\n解：令 |A-lambda I|=0。"},
        {"chunk_id": "k1", "content": "普通背景文字，没有明显角色。"},
    ]

    assert classify_chunk_role(chunks[0]["content"]) == "definition"
    assert classify_chunk_role(chunks[1]["content"]) == "example"

    roles = assign_chunk_roles(chunks, {"k1": "theorem"})
    assert roles == {"d1": "definition", "e1": "example", "k1": "theorem"}


def test_build_index_from_chapters_writes_role_metadata(monkeypatch, tmp_path):
    from ingestion import mineru_importer

    captured = []

    class FakeSplitter:
        def split_chapter(self, title, text):
            return [
                {"chapter": title, "chunk_index": 0, "content": "定义 群是满足运算封闭性的集合。", "chunk_id": "c_def"},
                {"chapter": title, "chunk_index": 1, "content": "例题 判断整数加法是否构成群。", "chunk_id": "c_ex"},
            ]

    class FakeVectorStore:
        def build_chapter_store(self, title, chunks, chunk_roles=None, book_name=""):
            captured.append((title, list(chunks), dict(chunk_roles or {}), book_name))

    monkeypatch.setattr(mineru_importer, "ChapterSplitter", FakeSplitter)
    monkeypatch.setattr(mineru_importer, "get_vector_store", lambda: FakeVectorStore())
    monkeypatch.setattr(mineru_importer, "load_kg_chunk_roles", lambda book_name: {"c_def": "theorem"})

    count = mineru_importer.build_index_from_chapters(
        "book",
        [{"title": "chapter 1", "text": "content", "page_number": 2}],
        tmp_path,
    )

    assert count == 2
    assert captured[0][2] == {"c_def": "theorem", "c_ex": "example"}
    assert captured[0][3] == "book"
    saved = json.loads((tmp_path / "book_middle_chunks.json").read_text(encoding="utf-8"))
    assert [chunk["role"] for chunk in saved] == ["theorem", "example"]
    assert saved[0]["page_idx"] == 1

def test_vector_store_collection_names_are_scoped_by_book():
    from ingestion.vector_store import ChapterVectorStore

    vs = ChapterVectorStore.__new__(ChapterVectorStore)
    chapter = "测试 章节"

    scoped_a = vs._chapter_collection_name(chapter, "book-a")
    scoped_b = vs._chapter_collection_name(chapter, "book-b")
    legacy = vs._chapter_collection_name(chapter, "")

    assert scoped_a.startswith("bk")
    assert scoped_b.startswith("bk")
    assert scoped_a != scoped_b
    assert legacy != scoped_a

    vs._map = {
        "legacy_col": {"chapter": chapter, "book_name": "", "schema_version": "1"},
        "scoped_col": {"chapter": chapter, "book_name": "book-a", "schema_version": "2"},
    }
    assert vs._title_to_collection(chapter, "book-a") == "scoped_col"
    assert vs._title_to_collection(chapter, "book-b") == "legacy_col"

