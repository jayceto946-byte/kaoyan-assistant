import io
from pathlib import Path

from fastapi import UploadFile
from PIL import Image

from backend.api import mistakes


def _upload(name: str, data: bytes) -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(data))


def test_uploaded_image_stays_pending_until_record_is_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(mistakes, "IMAGES_PATH", tmp_path / "images")

    pending_path = mistakes._save_uploaded_image(_upload("question.png", b"not-a-real-image"))
    assert pending_path.parent.name == "pending"
    assert pending_path.exists()

    committed_path, moved = mistakes._commit_pending_mistake_image(str(pending_path))
    committed = Path(committed_path)
    assert moved is True
    assert committed.parent == tmp_path / "images" / "mistakes"
    assert committed.exists()
    assert not pending_path.exists()


def test_image_cleanup_is_confined_to_mistake_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(mistakes, "IMAGES_PATH", tmp_path / "images")
    inside = tmp_path / "images" / "mistakes" / "inside.png"
    outside = tmp_path / "outside.png"
    inside.parent.mkdir(parents=True)
    inside.write_bytes(b"inside")
    outside.write_bytes(b"outside")

    mistakes._delete_mistake_image(inside)
    mistakes._delete_mistake_image(outside)

    assert not inside.exists()
    assert outside.exists()


def test_recognition_failure_removes_pending_image(tmp_path, monkeypatch):
    monkeypatch.setattr(mistakes, "IMAGES_PATH", tmp_path / "images")
    pending = tmp_path / "images" / "mistakes" / "pending" / "failed.png"
    pending.parent.mkdir(parents=True)
    pending.write_bytes(b"image")
    monkeypatch.setattr(mistakes, "_save_uploaded_image", lambda _file: pending)

    def fail_ocr(_path):
        raise RuntimeError("vision unavailable")

    monkeypatch.setattr(mistakes, "_ocr_image_with_kimi", fail_ocr)
    result = mistakes.recognize_mistake_image(_upload("failed.png", b"image"))

    assert result["success"] is False
    assert not pending.exists()


def test_successful_optimization_replaces_raw_upload(tmp_path):
    raw = tmp_path / "sample_raw.png"
    Image.new("RGB", (32, 24), color="white").save(raw)

    optimized = mistakes._optimize_for_ocr(raw)

    assert optimized.name == "sample_ocr.jpg"
    assert optimized.exists()
    assert not raw.exists()