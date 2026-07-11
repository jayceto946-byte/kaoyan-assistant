"""Lightweight chat conversation persistence and follow-up rewriting."""
from __future__ import annotations

import json
import re
import time
import threading
import uuid
from pathlib import Path

from config import PROGRESS_PATH
from utils.json_io import atomic_write_json
from utils.subject_catalog import normalize_subject_value, subject_matches

CONV_DIR = Path(PROGRESS_PATH) / "conversations"
_CONVERSATION_LOCKS = tuple(threading.RLock() for _ in range(64))


def _conversation_lock(conversation_id: str) -> threading.RLock:
    return _CONVERSATION_LOCKS[hash(conversation_id) % len(_CONVERSATION_LOCKS)]


def ensure_conversation_id(conversation_id: str = "") -> str:
    if conversation_id and re.match(r"^[\w\-.]{1,80}$", conversation_id):
        return conversation_id
    return f"conv_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


def _path(conversation_id: str) -> Path:
    CONV_DIR.mkdir(parents=True, exist_ok=True)
    return CONV_DIR / f"{conversation_id}.json"


def _read_payload(conversation_id: str) -> dict:
    path = _path(conversation_id)
    if not path.exists():
        return {"id": conversation_id, "messages": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"id": conversation_id, "messages": []}
    except Exception:
        return {"id": conversation_id, "messages": []}


def load_history(conversation_id: str) -> list[dict]:
    data = _read_payload(conversation_id)
    return data.get("messages", []) if isinstance(data, dict) else []


def append_message(conversation_id: str, role: str, content: str, book_name: str = "", subject: str = "") -> None:
    subject = normalize_subject_value(subject)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    with _conversation_lock(conversation_id):
        payload = _read_payload(conversation_id)
        history = payload.get("messages", []) if isinstance(payload, dict) else []
        history.append({
            "role": role,
            "content": content,
            "book_name": book_name,
            "subject": subject,
            "created_at": now,
        })
        payload = {
            "id": conversation_id,
            "messages": history[-40:],
            "subject": subject or payload.get("subject", ""),
            "book_name": book_name or payload.get("book_name", ""),
            "created_at": payload.get("created_at") or now,
            "updated_at": now,
        }
        atomic_write_json(_path(conversation_id), payload)

def get_conversation(conversation_id: str) -> dict:
    payload = _read_payload(ensure_conversation_id(conversation_id))
    messages = payload.get("messages", []) if isinstance(payload, dict) else []
    subject = payload.get("subject", "") or _last_meta(messages, "subject")
    book_name = payload.get("book_name", "") or _last_meta(messages, "book_name")
    return {
        "id": payload.get("id") or conversation_id,
        "subject": subject,
        "book_name": book_name,
        "messages": messages,
        "created_at": payload.get("created_at") or _first_meta(messages, "created_at"),
        "updated_at": payload.get("updated_at") or _last_meta(messages, "created_at"),
        "title": _conversation_title(messages),
    }


def list_conversations(subject: str = "", book_name: str = "", limit: int = 80) -> list[dict]:
    CONV_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    for path in CONV_DIR.glob("*.json"):
        conversation_id = path.stem
        item = get_conversation(conversation_id)
        if subject and not subject_matches(item.get("subject", ""), subject):
            continue
        if book_name and item.get("book_name") != book_name:
            continue
        if not item.get("messages"):
            continue
        items.append({
            "id": item["id"],
            "title": item["title"],
            "subject": item.get("subject", ""),
            "book_name": item.get("book_name", ""),
            "created_at": item.get("created_at", ""),
            "updated_at": item.get("updated_at", ""),
            "message_count": len(item.get("messages", [])),
        })
    items.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return items[: max(1, min(limit, 200))]


def _conversation_title(messages: list[dict]) -> str:
    for item in messages:
        if item.get("role") == "user":
            content = re.sub(r"\s+", " ", str(item.get("content", "")).strip())
            return content[:36] or "新会话"
    return "新会话"


def _last_meta(messages: list[dict], key: str) -> str:
    for item in reversed(messages):
        value = str(item.get(key, "")).strip()
        if value:
            return value
    return ""


def _first_meta(messages: list[dict], key: str) -> str:
    for item in messages:
        value = str(item.get(key, "")).strip()
        if value:
            return value
    return ""


def rewrite_followup(question: str, history: list[dict], book_name: str = "", subject: str = "") -> str:
    """Turn an explicit anaphoric follow-up into a compact retrieval query."""
    question = question.strip()
    if not history or not _looks_like_followup(question):
        return question
    previous_user = next(
        (_strip_internal_references(str(item.get("content", ""))) for item in reversed(history) if item.get("role") == "user" and str(item.get("content", "")).strip()),
        "",
    )
    if not previous_user:
        return question
    scope = " / ".join(value for value in (subject.strip(), book_name.strip()) if value)
    prefix = f"[{scope}] " if scope else ""
    return f"{prefix}{previous_user[:500]}；{question}"


def _looks_like_followup(question: str) -> bool:
    compact = re.sub(r"\s+", "", question)
    markers = [
        "\u8fd9\u4e2a", "\u90a3\u4e2a", "\u4e0a\u9762", "\u521a\u624d", "\u524d\u9762", "\u7ee7\u7eed",
        "\u8fd9\u91cc", "\u5b83", "\u5176", "\u8fd9\u4e00\u6b65", "\u518d\u89e3\u91ca", "\u5c55\u5f00", "\u8ffd\u95ee",
    ]
    return any(marker in compact for marker in markers)


def _strip_internal_references(text: str) -> str:
    text = re.sub(r"\s*/\s*[a-f0-9]{12,64}(?=\s*\])", "", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()
