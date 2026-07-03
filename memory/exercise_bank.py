"""Exercise bank storage.

The exercise bank is a general question asset layer. Mistakes can be copied into
this structure through origin_type/origin_id without changing the mistake book.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from utils.path_safety import safe_book_name, safe_child_path
from utils.subject_catalog import subject_matches
from typing import Any, Optional


@dataclass
class ExerciseRecord:
    question_text: str
    answer: str = ""
    explanation: str = ""
    source: str = ""
    subject: str = ""
    chapter: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    question_type: str = ""
    difficulty: int = 3
    image_path: Optional[str] = None
    ocr_text: str = ""
    linked_concepts: list[dict] = field(default_factory=list)
    origin_type: str = "manual"
    origin_id: str = ""
    status: str = "new"
    notes: str = ""
    last_practiced: Optional[str] = None
    practice_count: int = 0
    practice_history: list[dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ExerciseRecord":
        data = dict(data)
        if data.get("chapter") == "":
            data["chapter"] = None
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ExerciseBankStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.execute("PRAGMA busy_timeout = 15000")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS exercises (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    subject TEXT,
                    chapter TEXT,
                    source TEXT,
                    origin_type TEXT,
                    origin_id TEXT,
                    status TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ex_subject ON exercises(subject)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ex_chapter ON exercises(chapter)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ex_origin ON exercises(origin_type, origin_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ex_status ON exercises(status)")
            conn.commit()

    def add(self, record: ExerciseRecord) -> str:
        record.updated_at = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO exercises (id, data, created_at, updated_at, subject, chapter, source, origin_type, origin_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    json.dumps(record.to_dict(), ensure_ascii=False),
                    record.created_at,
                    record.updated_at,
                    record.subject,
                    record.chapter,
                    record.source,
                    record.origin_type,
                    record.origin_id,
                    record.status,
                ),
            )
            conn.commit()
        return record.id

    def get(self, rid: str) -> Optional[ExerciseRecord]:
        with self._connect() as conn:
            row = conn.execute("SELECT data FROM exercises WHERE id = ?", (rid,)).fetchone()
        return ExerciseRecord.from_dict(json.loads(row[0])) if row else None

    def find_by_origin(self, origin_type: str, origin_id: str) -> Optional[ExerciseRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM exercises WHERE origin_type = ? AND origin_id = ? LIMIT 1",
                (origin_type, origin_id),
            ).fetchone()
        return ExerciseRecord.from_dict(json.loads(row[0])) if row else None

    def update(self, record: ExerciseRecord):
        record.updated_at = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE exercises
                SET data = ?, updated_at = ?, subject = ?, chapter = ?, source = ?, origin_type = ?, origin_id = ?, status = ?
                WHERE id = ?
                """,
                (
                    json.dumps(record.to_dict(), ensure_ascii=False),
                    record.updated_at,
                    record.subject,
                    record.chapter,
                    record.source,
                    record.origin_type,
                    record.origin_id,
                    record.status,
                    record.id,
                ),
            )
            conn.commit()

    def delete(self, rid: str):
        with self._connect() as conn:
            conn.execute("DELETE FROM exercises WHERE id = ?", (rid,))
            conn.commit()

    def list_all(
        self,
        subject: Optional[str] = None,
        chapter: Optional[str] = None,
        tag: Optional[str] = None,
        search_kw: str = "",
        status: str = "",
        limit: int = 100,
    ) -> list[ExerciseRecord]:
        sql = "SELECT data FROM exercises WHERE 1=1"
        params: list[Any] = []
        if chapter:
            sql += " AND chapter = ?"
            params.append(chapter)
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit if not subject and not tag and not search_kw.strip() else max(limit * 10, 1000))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        records = [ExerciseRecord.from_dict(json.loads(row[0])) for row in rows]
        if subject:
            records = [r for r in records if subject_matches(r.subject, subject)]
        if tag:
            records = [r for r in records if tag in r.tags]
        if search_kw.strip():
            kw = search_kw.strip().lower()
            records = [
                r for r in records
                if kw in r.question_text.lower()
                or kw in r.answer.lower()
                or kw in r.explanation.lower()
                or kw in r.source.lower()
                or any(kw in tag.lower() for tag in r.tags)
            ]
        return records[:limit]

    def stats(self, subject: Optional[str] = None) -> dict:
        records = self.list_all(subject=subject, limit=10000)
        by_type: dict[str, int] = {}
        by_tag: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for record in records:
            if record.question_type:
                by_type[record.question_type] = by_type.get(record.question_type, 0) + 1
            by_status[record.status] = by_status.get(record.status, 0) + 1
            for tag in record.tags:
                by_tag[tag] = by_tag.get(tag, 0) + 1
        return {"total": len(records), "by_type": by_type, "by_tag": by_tag, "by_status": by_status}


class ExerciseBank:
    def __init__(self, db_path: str | Path):
        self.store = ExerciseBankStore(db_path)

    def add(self, record: ExerciseRecord) -> str:
        return self.store.add(record)

    def get(self, rid: str) -> Optional[ExerciseRecord]:
        return self.store.get(rid)

    def find_by_origin(self, origin_type: str, origin_id: str) -> Optional[ExerciseRecord]:
        return self.store.find_by_origin(origin_type, origin_id)

    def update(self, record: ExerciseRecord):
        self.store.update(record)

    def record_practice(self, rid: str, user_answer: str = "", quality: int = 0, add_note: str = "") -> Optional[ExerciseRecord]:
        record = self.get(rid)
        if not record:
            return None
        quality = max(0, min(5, int(quality)))
        practiced_at = datetime.now().isoformat()
        record.last_practiced = practiced_at
        record.practice_count += 1
        record.practice_history.append(
            {
                "date": practiced_at,
                "quality": quality,
                "user_answer": user_answer.strip(),
                "note": add_note.strip(),
            }
        )
        if quality >= 4:
            record.status = "mastered"
        elif quality >= 3:
            record.status = "practicing"
        else:
            record.status = "needs_review"
        self.update(record)
        return record

    def delete(self, rid: str):
        self.store.delete(rid)

    def list_all(self, **filters) -> list[ExerciseRecord]:
        return self.store.list_all(**filters)

    def stats(self, subject: Optional[str] = None) -> dict:
        return self.store.stats(subject=subject)


def get_exercise_bank(book_name: str = "default", data_dir: str = "./data/progress") -> ExerciseBank:
    return ExerciseBank(safe_child_path(data_dir, f"exercise_bank_{safe_book_name(book_name)}.db"))
