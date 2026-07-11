"""Conservative helpers for retrying SQLite initialization without data loss."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def prepare_sqlite_retry_files(db_path: str | Path) -> dict[str, list[str]]:
    """Remove only empty SQLite artifacts and preserve non-empty recovery files.

    A non-empty WAL or rollback journal may contain committed or recoverable
    transactions. Automatic startup recovery must never delete those files.
    """

    database = Path(db_path)
    removed: list[str] = []
    preserved: list[str] = []

    for candidate in [Path(f"{database}{suffix}") for suffix in ("-wal", "-shm", "-journal")]:
        if not candidate.exists():
            continue
        try:
            if candidate.stat().st_size == 0:
                candidate.unlink()
                removed.append(str(candidate))
            else:
                preserved.append(str(candidate))
        except OSError:
            preserved.append(str(candidate))

    try:
        if database.exists() and database.stat().st_size == 0:
            database.unlink()
            removed.append(str(database))
    except OSError:
        preserved.append(str(database))

    return {"removed": removed, "preserved": preserved}
