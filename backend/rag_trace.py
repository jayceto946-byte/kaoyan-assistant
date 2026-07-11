"""Small, bounded request traces for diagnosing local RAG latency and ranking."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

from config import PROGRESS_PATH

TRACE_DB_PATH = Path(PROGRESS_PATH) / "rag_traces.db"
MAX_TRACE_ROWS = 500


def _connect() -> sqlite3.Connection:
    TRACE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(TRACE_DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS rag_traces (request_id TEXT PRIMARY KEY, created_at REAL NOT NULL, conversation_id TEXT, book_name TEXT, question TEXT, intent TEXT, fast_path INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL, ttft_ms REAL, total_ms REAL, timings_json TEXT NOT NULL, evidence_json TEXT NOT NULL, error TEXT)")
    return conn


def new_request_id() -> str:
    return uuid.uuid4().hex


def save_trace(trace: dict) -> None:
    evidence = [{
        "chunk_id": str(item.get("chunk_id") or ""),
        "chapter": str(item.get("chapter") or ""),
        "section_title": str(item.get("section_title") or ""),
        "source": str(item.get("source") or ""),
        "score": item.get("final_score", item.get("score")),
    } for item in (trace.get("evidence") or [])[:20]]
    with _connect() as conn:
        conn.execute("INSERT OR REPLACE INTO rag_traces VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
            trace["request_id"], trace.get("created_at", time.time()), trace.get("conversation_id", ""),
            trace.get("book_name", ""), str(trace.get("question") or "")[:1000], trace.get("intent", ""),
            int(bool(trace.get("fast_path"))), trace.get("status", "done"), trace.get("ttft_ms"),
            trace.get("total_ms"), json.dumps(trace.get("timings") or {}, ensure_ascii=False),
            json.dumps(evidence, ensure_ascii=False), str(trace.get("error") or "")[:2000],
        ))
        conn.execute("DELETE FROM rag_traces WHERE request_id IN (SELECT request_id FROM rag_traces ORDER BY created_at DESC LIMIT -1 OFFSET ?)", (MAX_TRACE_ROWS,))


def list_traces(limit: int = 50) -> list[dict]:
    limit = max(1, min(int(limit), 200))
    if not TRACE_DB_PATH.exists():
        return []
    with sqlite3.connect(str(TRACE_DB_PATH), timeout=5) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM rag_traces ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["fast_path"] = bool(item["fast_path"])
        item["timings"] = json.loads(item.pop("timings_json") or "{}")
        item["evidence"] = json.loads(item.pop("evidence_json") or "[]")
        result.append(item)
    return result
