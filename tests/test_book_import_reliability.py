import io
from pathlib import Path

from fastapi import UploadFile


class _NoopLifecycle:
    def _delete_vector_assets(self, book_name):
        return []


def _isolate_paths(monkeypatch, books, staging, progress, mineru, vector):
    import backend.api.books as books_api

    monkeypatch.setattr(books_api, "BOOKS_PATH", books)
    monkeypatch.setattr(books_api, "BOOK_UPLOAD_DIR", staging)
    monkeypatch.setattr(books_api, "PROGRESS_PATH", progress)
    monkeypatch.setattr(books_api, "MINERU_OUTPUT_PATH", mineru)
    monkeypatch.setattr(books_api, "VECTOR_DB_PATH", vector)
    monkeypatch.setattr(books_api, "_lifecycle", _NoopLifecycle())
    return books_api


def test_pdf_upload_stays_out_of_library_until_promoted(monkeypatch, tmp_path):
    books_api = _isolate_paths(
        monkeypatch,
        tmp_path / "books",
        tmp_path / "staging",
        tmp_path / "progress",
        tmp_path / "mineru",
        tmp_path / "vector",
    )
    upload = UploadFile(file=io.BytesIO(b"%PDF-1.7 test"), filename="demo.pdf")

    staged = books_api._save_upload(upload)

    assert staged.parent == tmp_path / "staging"
    assert not (tmp_path / "books" / "demo.pdf").exists()
    final = books_api._promote_uploaded_pdf(staged)
    assert final == tmp_path / "books" / "demo.pdf"
    assert final.exists()
    assert not staged.exists()


def test_failed_new_import_cleanup_removes_all_new_artifacts(monkeypatch, tmp_path):
    books_api = _isolate_paths(
        monkeypatch,
        tmp_path / "books",
        tmp_path / "staging",
        tmp_path / "progress",
        tmp_path / "mineru",
        tmp_path / "vector",
    )
    staged = tmp_path / "staging" / "demo.pdf"
    final = tmp_path / "books" / "demo.pdf"
    progress = tmp_path / "progress" / "demo"
    output = tmp_path / "mineru" / "demo"
    lexical = tmp_path / "vector" / "_lexical" / "demo.json"
    for path in (staged, final, lexical):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("partial", encoding="utf-8")
    progress.mkdir(parents=True)
    output.mkdir(parents=True)
    (progress / "_chapters.json").write_text("[]", encoding="utf-8")
    (output / "partial.json").write_text("{}", encoding="utf-8")

    books_api._cleanup_new_book_import("demo", staged, final)

    assert not staged.exists()
    assert not final.exists()
    assert not progress.exists()
    assert not output.exists()
    assert not lexical.exists()


def test_external_import_name_never_reuses_existing_book(monkeypatch, tmp_path):
    books_api = _isolate_paths(
        monkeypatch,
        tmp_path / "books",
        tmp_path / "staging",
        tmp_path / "progress",
        tmp_path / "mineru",
        tmp_path / "vector",
    )
    (tmp_path / "books").mkdir()
    (tmp_path / "books" / "demo.pdf").write_bytes(b"%PDF")

    assert books_api._unique_new_book_name("demo") == "demo_1"


def test_pdf_upload_name_does_not_reuse_existing_book_without_pdf(monkeypatch, tmp_path):
    books_api = _isolate_paths(
        monkeypatch,
        tmp_path / "books",
        tmp_path / "staging",
        tmp_path / "progress",
        tmp_path / "mineru",
        tmp_path / "vector",
    )
    monkeypatch.setattr(books_api, "_known_book_names", lambda include_archived=True: ["demo"])
    upload = UploadFile(file=io.BytesIO(b"%PDF-1.7 test"), filename="demo.pdf")

    staged = books_api._save_upload(upload)

    assert staged.name == "demo_1.pdf"