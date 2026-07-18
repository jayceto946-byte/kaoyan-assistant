import json

import backend.book_lifecycle as lifecycle_module
from backend.book_lifecycle import BookLifecycleService
from memory.exercise_bank import ExerciseRecord, get_exercise_bank
from memory.mistake_book import MistakeRecord, get_mistake_book
from utils.book_registry import BookRegistry


def test_book_registry_keeps_id_across_display_rename_and_archive(tmp_path):
    registry = BookRegistry(tmp_path)
    created = registry.ensure("physical_name")
    renamed = registry.rename_display(created["book_id"], "新的展示名称")
    archived = registry.set_status(created["book_id"], "archived")

    assert renamed["book_id"] == created["book_id"]
    assert renamed["storage_name"] == "physical_name"
    assert archived["status"] == "archived"
    assert registry.resolve("新的展示名称")["book_id"] == created["book_id"]
    assert registry.resolve(created["book_id"], include_archived=False) is None


def test_lifecycle_rename_is_logical_and_restore_is_non_destructive(monkeypatch, tmp_path):
    progress = tmp_path / "progress"
    books = tmp_path / "books"
    mineru = tmp_path / "mineru"
    vector = tmp_path / "vector"
    for path in (progress, books, mineru, vector):
        path.mkdir()
    monkeypatch.setattr(lifecycle_module, "BOOKS_PATH", books)
    monkeypatch.setattr(lifecycle_module, "MINERU_OUTPUT_PATH", mineru)
    monkeypatch.setattr(lifecycle_module, "VECTOR_DB_PATH", vector)
    storage_dir = progress / "physical_name"
    storage_dir.mkdir()
    (storage_dir / "_chapters.json").write_text("[]", encoding="utf-8")
    (books / "physical_name.pdf").write_bytes(b"pdf")
    service = BookLifecycleService(progress)

    identity, _ = service.ensure_identity("physical_name")
    renamed, meta = service.rename_display(identity["book_id"], "展示名称")
    archived, _ = service.archive(identity["book_id"])
    restored, _ = service.restore(identity["book_id"])

    assert renamed["book_id"] == identity["book_id"]
    assert renamed["storage_name"] == "physical_name"
    assert meta["display_name"] == "展示名称"
    assert archived["status"] == "archived"
    assert restored["status"] == "active"
    assert storage_dir.exists()
    assert (books / "physical_name.pdf").exists()
    assert json.loads((storage_dir / "metadata.json").read_text(encoding="utf-8"))["book_id"] == identity["book_id"]


def test_new_exercise_and_mistake_records_receive_book_id(tmp_path):
    identity = BookRegistry(tmp_path).ensure("book")
    exercise_bank = get_exercise_bank("book", str(tmp_path))
    mistake_book = get_mistake_book("book", str(tmp_path))

    exercise = ExerciseRecord(question_text="题目")
    mistake = MistakeRecord(question_text="错题")
    exercise_bank.add(exercise)
    mistake_book.add(mistake)

    assert exercise.book_id == identity["book_id"]
    assert mistake.book_id == identity["book_id"]
    assert exercise_bank.get(exercise.id).book_id == identity["book_id"]
    assert mistake_book.get(mistake.id).book_id == identity["book_id"]


def test_purge_requires_exact_book_id(tmp_path):
    service = BookLifecycleService(tmp_path)
    identity, _ = service.ensure_identity("book")

    try:
        service.purge(identity["book_id"], confirmation="book")
    except ValueError as exc:
        assert "book_id" in str(exc)
    else:
        raise AssertionError("purge must require exact stable id")
