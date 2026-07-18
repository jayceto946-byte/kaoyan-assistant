import json
import zipfile

import pytest

from backend.data_backup import inspect_backup


def test_backup_rejects_declared_but_missing_core_file(tmp_path):
    archive_path = tmp_path / "missing_manifest_file.zip"
    manifest = {
        "schema_version": 2,
        "format": "kaoyan-learning-backup",
        "included": ["data/progress", "data/storage_manifest.json"],
        "file_count": 1,
        "uncompressed_bytes": 2,
        "contains_secrets": False,
    }
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("data/progress/state.json", "{}")

    with pytest.raises(ValueError, match="storage_manifest"):
        inspect_backup(archive_path)
