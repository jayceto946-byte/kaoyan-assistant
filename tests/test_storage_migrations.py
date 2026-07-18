import json
import zipfile

import backend.data_backup as data_backup
import memory.spaced_repetition as spaced_module
import memory.study_memory as study_module
from memory.study_memory import StudyMemory
from utils.storage_manifest import COMPONENT_VERSIONS, ensure_storage_manifest


def test_storage_manifest_upgrades_legacy_payload(tmp_path):
    path = tmp_path / "storage_manifest.json"
    path.write_text('{"components":{"study_memory":0}}', encoding="utf-8")

    manifest = ensure_storage_manifest(tmp_path)

    assert manifest["schema_version"] == 1
    assert manifest["components"]["study_memory"] == COMPONENT_VERSIONS["study_memory"]
    assert "authoritative" in manifest["data_classes"]
    assert json.loads(path.read_text(encoding="utf-8")) == manifest


def test_study_memory_keeps_legacy_shapes_and_uses_atomic_replacement(monkeypatch, tmp_path):
    monkeypatch.setattr(study_module, "PROGRESS_PATH", tmp_path)
    monkeypatch.setattr(spaced_module, "PROGRESS_PATH", tmp_path)
    memory = StudyMemory("book")

    memory.mark_chapter_studied("第一章")
    memory.add_quiz_record("第一章", "题目", "答案", True, score=100)
    memory.add_chat("user", "内容", "第一章")

    base = tmp_path / "book"
    assert isinstance(json.loads((base / "progress.json").read_text(encoding="utf-8")), dict)
    assert isinstance(json.loads((base / "quiz_history.json").read_text(encoding="utf-8")), list)
    assert isinstance(json.loads((base / "chat_history.json").read_text(encoding="utf-8")), list)
    assert not list(base.glob("*.tmp"))


def test_v1_backup_manifest_is_migrated_in_memory(tmp_path):
    archive_path = tmp_path / "learning_data_v1.zip"
    legacy = {
        "schema_version": 1,
        "app_version": "0.9.0",
        "included": ["data/progress"],
        "file_count": 1,
        "uncompressed_bytes": 2,
        "contains_secrets": False,
    }
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(legacy))
        archive.writestr("data/progress/state.json", "{}")

    inspected = data_backup.inspect_backup(archive_path)

    assert inspected["schema_version"] == 2
    assert inspected["original_schema_version"] == 1
    assert inspected["format"] == "kaoyan-learning-backup"


def test_v2_backup_contains_storage_manifest(monkeypatch, tmp_path):
    data_root = tmp_path / "data"
    backup_root = tmp_path / "backups"
    (data_root / "progress").mkdir(parents=True)
    (data_root / "progress" / "state.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(data_backup, "DATA_ROOT", data_root)
    monkeypatch.setattr(data_backup, "MINERU_ROOT", tmp_path / "mineru")
    monkeypatch.setattr(data_backup, "BACKUP_ROOT", backup_root)
    monkeypatch.setattr(data_backup, "PENDING_RESTORE_PATH", backup_root / "pending_restore.json")
    monkeypatch.setattr(data_backup, "RESTORE_RESULT_PATH", backup_root / "last_restore.json")

    result = data_backup.create_backup()

    with zipfile.ZipFile(backup_root / result["name"]) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
    assert "data/storage_manifest.json" in names
    assert manifest["schema_version"] == 2
    assert manifest["component_versions"]["book_registry"] == 1
