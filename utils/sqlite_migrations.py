"""Small, dependency-free SQLite schema migration runner."""
from __future__ import annotations

import sqlite3
from collections.abc import Callable


Migration = Callable[[sqlite3.Connection], None]


def apply_sqlite_migrations(
    conn: sqlite3.Connection,
    *,
    component: str,
    current_version: int,
    migrations: dict[int, Migration] | None = None,
) -> int:
    """Apply ordered, idempotent migrations and persist PRAGMA user_version.

    Migration keys are their destination version (for example key 2 upgrades
    version 1 to version 2). Version 1 can be a no-op for legacy databases whose
    initial tables were historically created without PRAGMA user_version.
    """
    row = conn.execute("PRAGMA user_version").fetchone()
    installed = int(row[0] if row else 0)
    if installed > current_version:
        raise RuntimeError(
            f"{component} database schema {installed} is newer than supported schema {current_version}"
        )
    steps = migrations or {}
    for target in range(installed + 1, current_version + 1):
        migration = steps.get(target)
        if migration:
            migration(conn)
        conn.execute(f"PRAGMA user_version = {target}")
    return current_version
