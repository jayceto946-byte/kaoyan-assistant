"""Persisted, dependency-free BM25 index used alongside Chroma."""
from __future__ import annotations

import json
import math
import re
import threading
from collections import Counter
from pathlib import Path

from config import VECTOR_DB_PATH
from utils.json_io import atomic_write_json
from utils.path_safety import safe_book_name

_cache = {}
_lock = threading.RLock()
_QUERY_STOP_TOKENS = {
    "\u54ea\u4e9b", "\u6709\u54ea", "\u7279\u70b9", "\u4e3b\u8981", "\u4ec0\u4e48", "\u4e3a\u4ec0", "\u4e48",
    "\u662f\u5426", "\u4e3a\u4f55", "\u8bf4\u660e", "\u7b80\u8ff0", "\u5217\u51fa", "\u5417",
}



def tokenize(text: str) -> list[str]:
    normalized = re.sub(r"\s+", "", (text or "").lower())
    terms = re.findall(r"[a-z0-9_.+-]+|[\u4e00-\u9fff]+", normalized)
    tokens = []
    for term in terms:
        if re.fullmatch(r"[\u4e00-\u9fff]+", term):
            tokens.append(term)
            tokens.extend(term[i:i + 2] for i in range(max(0, len(term) - 1)))
        else:
            tokens.append(term)
    return [token for token in tokens if token not in _QUERY_STOP_TOKENS]


def index_path(book_name: str) -> Path:
    return Path(VECTOR_DB_PATH) / "_lexical" / f"{safe_book_name(book_name)}.json"


def write_book_index(book_name: str, chunks: list[dict]) -> Path:
    path = index_path(book_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = (
        "chapter", "section_title", "section_path", "chunk_index", "chunk_id",
        "parent_id", "prev_chunk_id", "next_chunk_id", "page_idx", "role",
        "content", "retrieval_text", "parent_content", "subject", "book_role", "rag_priority",
        "bbox", "equations", "block_type", "source_markdown", "review_status",
    )
    atomic_write_json(path, [{key: chunk.get(key) for key in keys} for chunk in chunks])
    with _lock:
        _cache.pop(safe_book_name(book_name), None)
    return path


def load_book_index(book_name: str) -> list[dict]:
    path = index_path(book_name)
    if not path.exists():
        return []
    stamp = path.stat().st_mtime
    key = safe_book_name(book_name)
    with _lock:
        cached = _cache.get(key)
        if cached and cached[0] == stamp:
            return cached[1]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            rows = data if isinstance(data, list) else []
        except Exception:
            rows = []
        _cache[key] = (stamp, rows)
        return rows


def search_book(book_name: str, query: str, *, k: int = 20, chapters: list[str] | None = None) -> list[dict]:
    rows = load_book_index(book_name)
    if not rows:
        return []
    docs = [tokenize(str(row.get("retrieval_text") or row.get("content") or "")) for row in rows]
    query_tokens = tokenize(query)
    if not query_tokens:
        return []
    n = len(docs)
    avgdl = sum(len(doc) for doc in docs) / max(n, 1)
    df = Counter(token for doc in docs for token in set(doc))
    preferred = set(chapters or [])
    scored = []
    for idx, tokens in enumerate(docs):
        tf, dl, score = Counter(tokens), len(tokens), 0.0
        for token in query_tokens:
            freq = tf.get(token, 0)
            if not freq:
                continue
            idf = math.log(1 + (n - df[token] + 0.5) / (df[token] + 0.5))
            score += idf * (freq * 2.2) / (freq + 1.2 * (0.25 + 0.75 * dl / max(avgdl, 1)))
        if preferred and rows[idx].get("chapter") in preferred:
            score *= 1.2
        if score > 0:
            scored.append((score, idx))
    scored.sort(reverse=True)
    result = []
    for rank, (score, idx) in enumerate(scored[:k], 1):
        item = dict(rows[idx])
        item.update({
            "source": "bm25", "bm25_score": score,
            "retrieval_rank": rank, "text": item.get("content", ""),
            "is_direct_hit": False,
        })
        result.append(item)
    return result


def expand_neighbors(book_name: str, chunk_ids: list[str], window: int = 1) -> list[dict]:
    rows = load_book_index(book_name)
    positions = {str(row.get("chunk_id")): idx for idx, row in enumerate(rows)}
    selected = {}
    for chunk_id in chunk_ids:
        pos = positions.get(str(chunk_id))
        if pos is None:
            continue
        for idx in range(max(0, pos - window), min(len(rows), pos + window + 1)):
            row = dict(rows[idx])
            row["text"] = row.get("content", "")
            row["source"] = "neighbor" if idx != pos else "index"
            row["is_direct_hit"] = idx == pos
            selected[str(row.get("chunk_id"))] = row
    return list(selected.values())
