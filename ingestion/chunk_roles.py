"""Assign semantic roles to textbook chunks before vector indexing."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Mapping

ROLE_PRIORITY = {
    "definition": 0,
    "theorem": 1,
    "property": 2,
    "formula": 3,
    "derivation": 4,
    "proof": 5,
    "algorithm": 6,
    "example": 7,
    "exercise": 8,
    "reference": 99,
}

ROLE_ALIASES = {
    "axiom": "theorem",
    "lemma": "theorem",
    "corollary": "theorem",
    "proposition": "theorem",
    "method": "algorithm",
    "remark": "reference",
    "mention": "reference",
}

ROLE_PATTERNS: list[tuple[str, list[str]]] = [
    ("example", [r"(^|\n)\s*(例|例题|例\s*\d+|example\b)", r"(^|\n)\s*(解|解析)[:：]"]),
    ("exercise", [r"(^|\n)\s*(练习|习题|思考题|作业|exercise\b)", r"(^|\n)\s*\d+[.、]\s*证明"]),
    ("definition", [r"(定义|称为|叫做|记为|definition\b)", r"(若|如果).{0,40}(则称|称)"]),
    ("theorem", [r"(定理|命题|引理|推论|theorem\b|lemma\b|corollary\b|proposition\b)"]),
    ("property", [r"(性质|结论|特点|充分必要|充要条件|property\b)"]),
    ("proof", [r"(^|\n)\s*(证明|证)[:：]", r"proof\b"]),
    ("derivation", [r"(推导|推得|可得|得到|因此|所以|由.*得|derivation\b)"]),
    ("algorithm", [r"(算法|步骤|流程|方法|procedure\b|algorithm\b)", r"(第一步|第二步|步骤\s*\d+)"]),
    ("formula", [r"(公式|恒等式|方程|表达式|formula\b)"]),
]

MATH_MARKERS = ("$", "\\(", "\\[", "=", "\\frac", "\\sum", "\\int", "\\lim", "\\begin")


def load_kg_chunk_roles(book_name: str) -> dict[str, str]:
    """Load chunk_id -> role from the local KG if available."""
    try:
        from knowledge.knowledge_graph import get_kg

        kg = get_kg(book_name)
        roles = getattr(kg, "_chunk_role", {}) or {}
        return {str(chunk_id): normalize_role(role) for chunk_id, role in roles.items() if chunk_id}
    except Exception:
        return {}


def assign_chunk_roles(
    chunks: list[dict[str, Any]],
    kg_roles: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return ``{chunk_id: role}`` for vector-store metadata.

    KG roles are authoritative when a chunk id matches. New imports often do not
    have KG yet, so a deterministic rule-based classifier fills the gap.
    """
    kg_roles = kg_roles or {}
    assigned: dict[str, str] = {}
    for chunk in chunks:
        chunk_id = str(chunk.get("chunk_id") or "")
        if not chunk_id:
            continue
        kg_role = normalize_role(kg_roles.get(chunk_id, "")) if kg_roles else "reference"
        if kg_role != "reference":
            assigned[chunk_id] = kg_role
            continue
        assigned[chunk_id] = classify_chunk_role(_chunk_text(chunk))
    return assigned


def classify_chunk_role(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "reference"

    scores: dict[str, int] = {}
    for role, patterns in ROLE_PATTERNS:
        score = 0
        for pattern in patterns:
            hits = re.findall(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
            score += len(hits)
        if score:
            scores[role] = score

    if _looks_formula_heavy(text):
        scores["formula"] = scores.get("formula", 0) + 1
    if "proof" in scores and scores.get("theorem"):
        scores["theorem"] += 1

    if not scores:
        return "reference"
    return min(scores, key=lambda role: (-scores[role], ROLE_PRIORITY.get(role, 99)))


def role_distribution(roles: Mapping[str, str]) -> dict[str, int]:
    return dict(Counter(roles.values()))


def normalize_role(role: Any) -> str:
    value = str(role or "").strip().lower()
    if not value:
        return "reference"
    value = ROLE_ALIASES.get(value, value)
    return value if value in ROLE_PRIORITY else "reference"


def _chunk_text(chunk: Mapping[str, Any]) -> str:
    for key in ("content", "text", "markdown"):
        value = chunk.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _looks_formula_heavy(text: str) -> bool:
    marker_count = sum(text.count(marker) for marker in MATH_MARKERS)
    if marker_count >= 3:
        return True
    if re.search(r"[A-Za-z]\s*=\s*[-+]?\w", text) and len(text) < 1200:
        return True
    return False