import io
import zipfile

import pytest


def test_limited_copy_removes_partial_oversized_file(monkeypatch, tmp_path):
    import utils.resource_limits as limits

    monkeypatch.setattr(limits, "MIN_FREE_DISK_BYTES", 0)
    target = tmp_path / "upload.bin"
    with pytest.raises(ValueError, match="size limit"):
        limits.copy_stream_limited(io.BytesIO(b"12345"), target, max_bytes=4)
    assert not target.exists()


def test_archive_limits_reject_file_count_and_compression_bomb(tmp_path):
    from utils.resource_limits import inspect_zip_limits

    many = tmp_path / "many.zip"
    with zipfile.ZipFile(many, "w") as archive:
        archive.writestr("one.txt", "1")
        archive.writestr("two.txt", "2")
    with zipfile.ZipFile(many) as archive, pytest.raises(ValueError, match="more than"):
        inspect_zip_limits(archive, max_files=1)

    bomb = tmp_path / "bomb.zip"
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("large.txt", b"0" * (2 * 1024 * 1024))
    with zipfile.ZipFile(bomb) as archive, pytest.raises(ValueError, match="compression ratio"):
        inspect_zip_limits(archive, max_ratio=10)


def test_archive_limits_reject_oversized_member(tmp_path):
    from utils.resource_limits import inspect_zip_limits

    archive_path = tmp_path / "member.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("large.txt", b"12345")
    with zipfile.ZipFile(archive_path) as archive, pytest.raises(ValueError, match="member exceeds"):
        inspect_zip_limits(archive, max_member_bytes=4)


def test_docx_rejects_oversized_xml_member(monkeypatch, tmp_path):
    import memory.exercise_file_importer as importer

    path = tmp_path / "large.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", b"<document>large</document>")
    monkeypatch.setattr(importer, "MAX_DOCX_MEMBER_BYTES", 10)

    with pytest.raises(ValueError, match="member exceeds"):
        importer.extract_docx_text(path)
