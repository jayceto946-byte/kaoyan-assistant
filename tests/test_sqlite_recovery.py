from utils.sqlite_recovery import prepare_sqlite_retry_files


def test_sqlite_retry_preserves_non_empty_recovery_files(tmp_path):
    database = tmp_path / "learning.sqlite3"
    wal = tmp_path / "learning.sqlite3-wal"
    shm = tmp_path / "learning.sqlite3-shm"
    journal = tmp_path / "learning.sqlite3-journal"

    database.write_bytes(b"database")
    wal.write_bytes(b"committed-wal-data")
    shm.write_bytes(b"")
    journal.write_bytes(b"rollback-data")

    result = prepare_sqlite_retry_files(database)

    assert database.read_bytes() == b"database"
    assert wal.read_bytes() == b"committed-wal-data"
    assert journal.read_bytes() == b"rollback-data"
    assert not shm.exists()
    assert str(wal) in result["preserved"]
    assert str(journal) in result["preserved"]
    assert str(shm) in result["removed"]


def test_sqlite_retry_removes_only_empty_database(tmp_path):
    database = tmp_path / "empty.sqlite3"
    database.write_bytes(b"")

    result = prepare_sqlite_retry_files(database)

    assert not database.exists()
    assert result["preserved"] == []
    assert str(database) in result["removed"]
