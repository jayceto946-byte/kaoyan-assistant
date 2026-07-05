from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
DELIVERABLES = ROOT / "data" / "imports" / "kaoyan_ocr_20260704" / "deliverables"

BOOKS = {
    "sensor_core": {
        "chunks": "sensor_core_chunks.jsonl",
        "out": "kg_candidates_sensor_core.jsonl",
        "book_name": "传感器短书",
        "subject": "传感器",
        "source_book": "CGQ_1",
    },
    "error_theory": {
        "chunks": "error_theory_chunks.jsonl",
        "out": "kg_candidates_error_theory.jsonl",
        "book_name": "误差理论与数据处理",
        "subject": "误差理论与数据处理",
        "source_book": "WC",
    },
}

LINK_OUT = "concept_links_sensor.jsonl"
REVIEW_OUT = "kg_review_queue.jsonl"
ALLOWED_LINK_TYPES = {
    "same_concept",
    "expansion",
    "proof",
    "condition",
    "edge_case",
    "example_more",
    "background",
}
CORE_ROLES = {"definition", "formula", "theorem", "derivation", "example", "exercise"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def processed_chunk_ids(path: Path) -> set[str]:
    ids = set()
    for row in load_jsonl(path):
        if row.get("error"):
            continue
        chunk_id = row.get("chunk_id") or row.get("reference_chunk_id")
        if chunk_id:
            ids.add(str(chunk_id))
    return ids


def strip_thinking(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL)
    return text.strip()


def parse_json_object(text: str) -> dict[str, Any]:
    clean = strip_thinking(text)
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", clean.strip(), flags=re.IGNORECASE | re.DOTALL)
    try:
        data = json.loads(clean)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        pass
    start = clean.find("{")
    end = clean.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(clean[start : end + 1])
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def normalize_list(value: Any, limit: int = 8) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    result = []
    seen = set()
    for item in value:
        if isinstance(item, str):
            item = item.strip()
        if not item:
            continue
        key = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, dict) else str(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def chunk_excerpt(text: str, max_chars: int = 2600) -> str:
    text = re.sub(r"\n{3,}", "\n\n", str(text or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 80] + "\n...\n" + text[-80:]


def should_extract(row: dict[str, Any]) -> bool:
    role = str(row.get("semantic_role") or "").strip()
    text = str(row.get("text") or "").strip()
    if not text or len(text) < 40:
        return False
    return role in CORE_ROLES


def make_client() -> tuple[OpenAI, str]:
    load_dotenv()
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured.")
    base_url = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
    model = os.getenv("DEEPSEEK_KG_MODEL") or os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-v4-pro")
    return OpenAI(api_key=api_key, base_url=base_url), model


def llm_json(client: OpenAI, model: str, system: str, user: str, retries: int = 3) -> dict[str, Any]:
    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0.1,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                extra_body={"reasoning_effort": "high", "thinking": {"type": "enabled"}},
                timeout=180,
            )
            data = parse_json_object(resp.choices[0].message.content or "")
            if data:
                return data
            last_error = "empty_or_invalid_json"
        except Exception as exc:
            last_error = str(exc)
        if attempt < retries:
            time.sleep(2 * attempt)
    return {"concepts": [], "_error": last_error}


CORE_SYSTEM = """你是考研测控教材知识图谱抽取助手。只基于给定教材 chunk 抽取，不要凭常识补充。输出必须是严格 JSON 对象，不要 Markdown，不要解释，不要 thinking。

JSON 格式：
{
  "concepts": [
    {
      "concept_name": "核心概念名",
      "aliases": ["别名"],
      "definition": "原文支持的简洁定义；没有则为空字符串",
      "formulas": [{"latex": "公式 LaTeX 或原式", "meaning": "公式含义"}],
      "properties": ["定理/性质/结论"],
      "conditions": ["适用条件/限制"],
      "misconceptions": ["常见误区或易混点；原文没有则空"],
      "example_locations": ["例题/应用/习题位置"],
      "prerequisites": ["前置概念"],
      "related_concepts": ["相关概念"],
      "evidence": "最能支撑该概念的原文短句",
      "confidence": 0.0
    }
  ]
}

规则：
1. 每个 chunk 最多抽 5 个高价值概念；目录、前言、版权页通常返回空数组。
2. confidence 取 0 到 1；定义/公式/定理证据明确的概念应高于 0.75。
3. 概念名必须是教材术语，不要抽“方法”“步骤”“系统”等泛词。
"""


def normalize_concept(raw: dict[str, Any], row: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    name = str(raw.get("concept_name") or raw.get("name") or "").strip()
    confidence = raw.get("confidence", 0)
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "concept_name": name,
        "aliases": normalize_list(raw.get("aliases"), 6),
        "definition": str(raw.get("definition") or "").strip(),
        "formulas": normalize_list(raw.get("formulas"), 6),
        "properties": normalize_list(raw.get("properties"), 6),
        "conditions": normalize_list(raw.get("conditions"), 6),
        "misconceptions": normalize_list(raw.get("misconceptions"), 4),
        "example_locations": normalize_list(raw.get("example_locations"), 4),
        "prerequisites": normalize_list(raw.get("prerequisites"), 6),
        "related_concepts": normalize_list(raw.get("related_concepts"), 8),
        "evidence": str(raw.get("evidence") or "").strip()[:600],
        "confidence": confidence,
        "chunk_id": str(row.get("chunk_id") or ""),
        "chapter_title": str(row.get("title") or ""),
        "semantic_role": str(row.get("semantic_role") or ""),
        "source_book": meta["source_book"],
        "book_name": meta["book_name"],
        "subject": meta["subject"],
        "review_status": "machine_generated" if confidence >= 0.72 else "needs_review",
    }


def extract_core_book(client: OpenAI, model: str, deliverables: Path, book_id: str, limit: int | None) -> None:
    meta = BOOKS[book_id]
    source = deliverables / meta["chunks"]
    output = deliverables / meta["out"]
    review_output = deliverables / REVIEW_OUT
    done = processed_chunk_ids(output)
    rows = [row for row in load_jsonl(source) if should_extract(row) and str(row.get("chunk_id")) not in done]
    if limit is not None:
        rows = rows[:limit]
    print(f"[{book_id}] pending chunks: {len(rows)} -> {output}", flush=True)

    batch_size = 4
    batch_system = CORE_SYSTEM + """

本次会给你多个 chunk。输出格式改为严格 JSON 对象：
{
  "chunks": [
    {"chunk_id": "原 chunk_id", "concepts": [上述 concept 对象]}
  ]
}
每个输入 chunk 都必须返回一项；没有概念时 concepts 为空数组。
"""

    for batch_start in range(0, len(rows), batch_size):
        batch = rows[batch_start:batch_start + batch_size]
        prompt_parts = [f"教材：{meta['book_name']}", f"学科：{meta['subject']}", "请分别抽取以下 chunk："]
        for row in batch:
            prompt_parts.append(
                "\n--- chunk ---\n"
                f"chunk_id：{row.get('chunk_id')}\n"
                f"章节标题：{row.get('title')}\n"
                f"语义角色：{row.get('semantic_role')}\n"
                f"正文：\n{chunk_excerpt(row.get('text', ''), max_chars=1800)}"
            )
        data = llm_json(client, model, batch_system, "\n".join(prompt_parts))
        by_chunk: dict[str, list[dict[str, Any]]] = {}
        if isinstance(data.get("chunks"), list):
            for item in data.get("chunks", []):
                if isinstance(item, dict):
                    by_chunk[str(item.get("chunk_id") or "")] = normalize_list(item.get("concepts"), 5)
        elif isinstance(data.get("concepts"), list) and len(batch) == 1:
            by_chunk[str(batch[0].get("chunk_id") or "")] = normalize_list(data.get("concepts"), 5)

        for offset, row in enumerate(batch, 1):
            raw_concepts = by_chunk.get(str(row.get("chunk_id") or ""), [])
            concepts = []
            for raw in raw_concepts:
                if isinstance(raw, dict):
                    item = normalize_concept(raw, row, meta)
                    if item["concept_name"] and len(item["concept_name"]) >= 2:
                        concepts.append(item)
            out_row = {
                "chunk_id": str(row.get("chunk_id") or ""),
                "book_id": book_id,
                "source_book": meta["source_book"],
                "chapter_title": str(row.get("title") or ""),
                "semantic_role": str(row.get("semantic_role") or ""),
                "concepts": concepts,
                "error": data.get("_error", ""),
            }
            append_jsonl(output, out_row)
            for concept in concepts:
                if concept["review_status"] == "needs_review":
                    append_jsonl(review_output, {"reason": "low_confidence_concept", **concept})
            index = batch_start + offset
            print(f"[{book_id}] {index}/{len(rows)} {row.get('chunk_id')} concepts={len(concepts)}", flush=True)
        time.sleep(0.5)

def load_core_concept_index(deliverables: Path) -> list[dict[str, Any]]:
    concepts = []
    seen = set()
    for row in load_jsonl(deliverables / BOOKS["sensor_core"]["out"]):
        for concept in row.get("concepts", []):
            name = str(concept.get("concept_name") or "").strip()
            if not name or name in seen or float(concept.get("confidence") or 0) < 0.72:
                continue
            seen.add(name)
            concepts.append({
                "concept_name": name,
                "aliases": concept.get("aliases", []),
                "core_chunk_id": concept.get("chunk_id", row.get("chunk_id", "")),
                "chapter_title": concept.get("chapter_title", ""),
            })
    return concepts


LINK_SYSTEM = """你是教材概念挂接助手。任务：判断“传感器长书”的 chunk 是否可以挂接到“传感器短书”的核心概念下。只基于给定文本和候选概念判断。
输出严格 JSON 对象：
{
  "links": [
    {
      "concept_name": "必须来自候选核心概念",
      "relation_to_core": "same_concept|expansion|proof|condition|edge_case|example_more|background",
      "use_when": ["definition", "detail", "derivation", "example", "condition", "review"],
      "evidence": "原文证据短句",
      "confidence": 0.0
    }
  ]
}
规则：
1. 没有明确相关性则返回空数组。
2. 每个 chunk 最多挂接 3 条。
3. 不要创造候选列表之外的核心概念名。
"""


def select_candidate_concepts(core_index: list[dict[str, Any]], text: str, limit: int = 20) -> list[dict[str, Any]]:
    scored = []
    for item in core_index:
        terms = [item["concept_name"], *item.get("aliases", [])]
        score = sum(1 for term in terms if term and str(term) in text)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], len(pair[1]["concept_name"])))
    return [item for _, item in scored[:limit]]


def link_sensor_reference(client: OpenAI, model: str, deliverables: Path, limit: int | None) -> None:
    core_index = load_core_concept_index(deliverables)
    if not core_index:
        print("[sensor_reference] no core concepts available; skip linking", flush=True)
        return
    source = deliverables / "sensor_reference_chunks.jsonl"
    output = deliverables / LINK_OUT
    review_output = deliverables / REVIEW_OUT
    done = processed_chunk_ids(output)
    rows = []
    for row in load_jsonl(source):
        chunk_id = str(row.get("chunk_id") or "")
        title = str(row.get("title") or "")
        role = str(row.get("semantic_role") or "").strip()
        text = title + "\n" + str(row.get("text") or "")
        if chunk_id in done or len(text) < 80 or role not in CORE_ROLES:
            continue
        if re.search(r"(封面|版权|前言|目录|内容简介|编目|第[一二三四五六七八九十0-9]+版前言)", title):
            continue
        candidates = select_candidate_concepts(core_index, text)
        if candidates:
            rows.append((row, candidates))
    if limit is not None:
        rows = rows[:limit]
    print(f"[sensor_reference] pending chunks: {len(rows)} -> {output}", flush=True)

    batch_size = 4
    batch_system = LINK_SYSTEM + """

本次会给你多个长书 chunk。输出格式改为严格 JSON 对象：
{
  "chunks": [
    {"reference_chunk_id": "原 reference_chunk_id", "links": [上述 link 对象]}
  ]
}
每个输入 chunk 都必须返回一项；没有明确挂接时 links 为空数组。
"""

    for batch_start in range(0, len(rows), batch_size):
        batch = rows[batch_start:batch_start + batch_size]
        prompt_parts = ["请分别判断以下长书 chunk 能否挂接到对应候选核心概念："]
        for row, candidates in batch:
            prompt_parts.append(
                "\n--- reference chunk ---\n"
                f"reference_chunk_id：{row.get('chunk_id')}\n"
                f"章节标题：{row.get('title')}\n"
                f"语义角色：{row.get('semantic_role')}\n"
                f"候选核心概念：\n{json.dumps(candidates, ensure_ascii=False)}\n"
                f"长书正文：\n{chunk_excerpt(row.get('text', ''), max_chars=1700)}"
            )
        data = llm_json(client, model, batch_system, "\n".join(prompt_parts))
        by_chunk: dict[str, list[dict[str, Any]]] = {}
        if isinstance(data.get("chunks"), list):
            for item in data.get("chunks", []):
                if isinstance(item, dict):
                    by_chunk[str(item.get("reference_chunk_id") or "")] = normalize_list(item.get("links"), 3)
        elif isinstance(data.get("links"), list) and len(batch) == 1:
            by_chunk[str(batch[0][0].get("chunk_id") or "")] = normalize_list(data.get("links"), 3)

        for offset, (row, candidates) in enumerate(batch, 1):
            candidate_by_name = {item["concept_name"]: item for item in candidates}
            links = []
            for raw in by_chunk.get(str(row.get("chunk_id") or ""), []):
                if not isinstance(raw, dict):
                    continue
                name = str(raw.get("concept_name") or "").strip()
                core = candidate_by_name.get(name)
                relation = str(raw.get("relation_to_core") or "").strip()
                try:
                    confidence = max(0.0, min(1.0, float(raw.get("confidence") or 0)))
                except (TypeError, ValueError):
                    confidence = 0.0
                if not core or relation not in ALLOWED_LINK_TYPES:
                    continue
                link = {
                    "concept_name": name,
                    "core_chunk_id": core.get("core_chunk_id", ""),
                    "reference_chunk_id": str(row.get("chunk_id") or ""),
                    "relation_to_core": relation,
                    "use_when": normalize_list(raw.get("use_when"), 6),
                    "evidence": str(raw.get("evidence") or "").strip()[:600],
                    "confidence": confidence,
                    "reference_chapter_title": str(row.get("title") or ""),
                    "semantic_role": str(row.get("semantic_role") or ""),
                    "source_book": "CGQ_2",
                    "review_status": "machine_generated" if confidence >= 0.72 else "needs_review",
                }
                links.append(link)
            if links:
                for link in links:
                    append_jsonl(output, link)
                    if link["review_status"] == "needs_review":
                        append_jsonl(review_output, {"reason": "low_confidence_link", **link})
            else:
                append_jsonl(output, {
                    "reference_chunk_id": str(row.get("chunk_id") or ""),
                    "source_book": "CGQ_2",
                    "links": [],
                    "review_status": "no_match",
                })
            index = batch_start + offset
            print(f"[sensor_reference] {index}/{len(rows)} {row.get('chunk_id')} links={len(links)}", flush=True)
        time.sleep(0.5)

def main() -> None:
    parser = argparse.ArgumentParser(description="Extract KG candidates for imported kaoyan OCR books.")
    parser.add_argument("--deliverables", type=Path, default=DELIVERABLES)
    parser.add_argument("--book", choices=["sensor_core", "error_theory", "sensor_reference"], action="append")
    parser.add_argument("--limit", type=int, default=None, help="Limit pending chunks per selected task.")
    args = parser.parse_args()

    client, model = make_client()
    selected = args.book or ["sensor_core", "error_theory", "sensor_reference"]
    for book_id in selected:
        if book_id == "sensor_reference":
            link_sensor_reference(client, model, args.deliverables, args.limit)
        else:
            extract_core_book(client, model, args.deliverables, book_id, args.limit)


if __name__ == "__main__":
    main()
