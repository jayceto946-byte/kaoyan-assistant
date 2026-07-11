"""Local RAG evaluation for retrieval, context quality, and answer quality."""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from graph.main_graph import run_graph_stream  # noqa: E402
from graph.retrieval_node import retrieve_node  # noqa: E402
from graph.safe_retrieval import get_safe_kg  # noqa: E402

DEFAULT_GOLDEN = ROOT / "data" / "eval" / "rag_golden_optimization.jsonl"
DEFAULT_REPORT = ROOT / "data" / "eval" / "rag_eval_report.json"
DEFAULT_BOOK = "\u4f18\u5316\u8bbe\u8ba1"


@dataclass
class EvalSample:
    question: str
    book_name: str = "default"
    intent: str = "qa"
    expected_chunk_ids: list[str] = field(default_factory=list)
    expected_chapter: str = ""
    expected_concepts: list[str] = field(default_factory=list)
    expected_keywords: list[str] = field(default_factory=list)
    reference_answer: str = ""
    target_chapters: list[str] = field(default_factory=list)
    answerable: bool = True
    forbidden_chunk_ids: list[str] = field(default_factory=list)
    expected_pages: list[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "EvalSample":
        return cls(
            question=str(raw.get("question") or ""),
            book_name=str(raw.get("book_name") or "default"),
            intent=str(raw.get("intent") or "qa"),
            expected_chunk_ids=list(raw.get("expected_chunk_ids") or []),
            expected_chapter=str(raw.get("expected_chapter") or ""),
            expected_concepts=list(raw.get("expected_concepts") or []),
            expected_keywords=list(raw.get("expected_keywords") or []),
            reference_answer=str(raw.get("reference_answer") or ""),
            target_chapters=list(raw.get("target_chapters") or []),
            answerable=bool(raw.get("answerable", True)),
            forbidden_chunk_ids=list(raw.get("forbidden_chunk_ids") or []),
            expected_pages=[int(page) for page in (raw.get("expected_pages") or [])],
        )


def read_jsonl(path: Path) -> list[EvalSample]:
    samples: list[EvalSample] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                sample = EvalSample.from_dict(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no} is not valid JSONL: {exc}") from exc
            if sample.question:
                samples.append(sample)
    return samples


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def retrieve_candidates(sample: EvalSample) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    state = {
        "user_input": sample.question,
        "book_name": sample.book_name,
        "intent": sample.intent,
        "target_chapters": sample.target_chapters,
        "use_textbook_context": True,
        "retrieval_error": "",
    }
    result = retrieve_node(state)
    return list(result.get("retrieval_debug_items") or []), {
        "matched_concepts": result.get("matched_concepts", []),
        "retrieval_status": result.get("retrieval_status", "ok"),
        "retrieval_error": result.get("retrieval_error", ""),
        "content_count": len(result.get("chapter_contents", {})),
    }


def _first_hit_rank(candidates: list[dict[str, Any]], expected: set[str]) -> int | None:
    if not expected:
        return None
    for idx, item in enumerate(candidates, 1):
        if item.get("chunk_id") in expected:
            return idx
    return None


def retrieval_metrics(sample: EvalSample, candidates: list[dict[str, Any]], cutoffs: list[int]) -> dict[str, Any]:
    expected = set(sample.expected_chunk_ids)
    rank = _first_hit_rank(candidates, expected)
    forbidden = set(sample.forbidden_chunk_ids)
    ids = [str(item.get("chunk_id") or "") for item in candidates]
    metrics: dict[str, Any] = {
        "expected_chunk_count": len(expected),
        "first_hit_rank": rank,
        "mrr": 0.0 if rank is None else 1.0 / rank,
        "answerable": sample.answerable,
        "forbidden_hits": [chunk_id for chunk_id in ids if chunk_id in forbidden],
        "page_hit": None if not sample.expected_pages else any(
            int(item.get("page_idx", item.get("page", -1))) in sample.expected_pages
            for item in candidates
            if str(item.get("page_idx", item.get("page", ""))).lstrip("-").isdigit()
        ),
    }
    for cutoff in cutoffs:
        top_ids = set(ids[:cutoff])
        hit_count = len(expected & top_ids)
        metrics[f"hit@{cutoff}"] = 1.0 if hit_count else 0.0
        metrics[f"recall@{cutoff}"] = (hit_count / len(expected)) if expected else None
    return metrics


def _tokens(text: str) -> set[str]:
    return {p for p in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text.lower()) if p.strip()}


def context_quality(sample: EvalSample, candidates: list[dict[str, Any]], top_k: int) -> dict[str, Any]:
    top = candidates[:top_k]
    context = "\n".join(str(item.get("preview") or "") for item in top)
    query_tokens = _tokens(sample.question)
    context_tokens = _tokens(context)
    expected_terms = set(sample.expected_keywords + sample.expected_concepts)
    keyword_hits = [term for term in expected_terms if term and term.lower() in context.lower()]
    chapter_hit = None
    if sample.expected_chapter:
        chapter_hit = any(
            sample.expected_chapter in str(item.get("chapter") or "")
            or sample.expected_chapter in str(item.get("section_title") or "")
            for item in top
        )
    return {
        "top_k": top_k,
        "context_chars": len(context),
        "query_token_coverage": len(query_tokens & context_tokens) / max(len(query_tokens), 1),
        "expected_keyword_coverage": len(set(keyword_hits)) / max(len(expected_terms), 1),
        "expected_chapter_hit": chapter_hit,
    }


def answer_quality(sample: EvalSample, answer: str, candidates: list[dict[str, Any]], top_k: int) -> dict[str, Any]:
    context = "\n".join(str(item.get("preview") or "") for item in candidates[:top_k])
    answer_tokens = _tokens(answer)
    context_tokens = _tokens(context)
    ref_tokens = _tokens(sample.reference_answer)
    expected_terms = set(sample.expected_keywords + sample.expected_concepts)
    expected_hits = [term for term in expected_terms if term and term.lower() in answer.lower()]
    return {
        "answer_chars": len(answer),
        "answer_context_overlap": len(answer_tokens & context_tokens) / max(len(answer_tokens), 1),
        "reference_answer_overlap": (len(answer_tokens & ref_tokens) / max(len(ref_tokens), 1)) if ref_tokens else None,
        "expected_term_coverage": len(set(expected_hits)) / max(len(expected_terms), 1),
    }


def run_answer_generation(sample: EvalSample) -> tuple[str, str]:
    chunks: list[str] = []
    try:
        for event in run_graph_stream(
            sample.question,
            book_name=sample.book_name,
            target_chapters=sample.target_chapters,
            use_textbook_context=True,
        ):
            if event.get("stage") == "generate" and event.get("chunk"):
                if event.get("replace"):
                    chunks = [str(event.get("chunk") or "")]
                else:
                    chunks.append(str(event.get("chunk") or ""))
    except Exception as exc:
        return "", str(exc)
    return "".join(chunks), ""


def _mean(values: list[float | None]) -> float | None:
    nums = [v for v in values if v is not None and not math.isnan(v)]
    return None if not nums else sum(nums) / len(nums)


def summarize(rows: list[dict[str, Any]], cutoffs: list[int]) -> dict[str, Any]:
    layer1: dict[str, Any] = {}
    for cutoff in cutoffs:
        layer1[f"hit@{cutoff}"] = _mean([r["layer1"].get(f"hit@{cutoff}") for r in rows])
        layer1[f"recall@{cutoff}"] = _mean([r["layer1"].get(f"recall@{cutoff}") for r in rows])
    layer1["mrr"] = _mean([r["layer1"].get("mrr") for r in rows])
    layer2 = {
        "query_token_coverage": _mean([r["layer2"].get("query_token_coverage") for r in rows]),
        "expected_keyword_coverage": _mean([r["layer2"].get("expected_keyword_coverage") for r in rows]),
        "expected_chapter_hit_rate": _mean([
            1.0 if r["layer2"].get("expected_chapter_hit") else 0.0
            for r in rows
            if r["layer2"].get("expected_chapter_hit") is not None
        ]),
    }
    generated = [r for r in rows if r.get("layer3") and not r.get("generation_error")]
    layer3 = {
        "generated_count": len(generated),
        "answer_context_overlap": _mean([r["layer3"].get("answer_context_overlap") for r in generated]),
        "reference_answer_overlap": _mean([r["layer3"].get("reference_answer_overlap") for r in generated]),
        "expected_term_coverage": _mean([r["layer3"].get("expected_term_coverage") for r in generated]),
    }
    return {
        "sample_count": len(rows),
        "retrieval_status": dict(Counter(r["retrieval_meta"].get("retrieval_status") for r in rows)),
        "layer1_retrieval": layer1,
        "latency": {"mean_retrieval_ms": _mean([r.get("retrieval_ms") for r in rows])},
        "layer2_context": layer2,
        "layer3_answer": layer3,
    }


def run_eval(args: argparse.Namespace) -> dict[str, Any]:
    samples = read_jsonl(Path(args.golden))
    if args.limit:
        samples = samples[: args.limit]
    cutoffs = sorted({int(k) for k in args.cutoffs.split(",") if k.strip()})
    rows: list[dict[str, Any]] = []
    by_intent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    started = time.time()
    for idx, sample in enumerate(samples, 1):
        retrieval_started = time.perf_counter()
        candidates, meta = retrieve_candidates(sample)
        retrieval_ms = round((time.perf_counter() - retrieval_started) * 1000, 2)
        row = {
            "index": idx,
            "question": sample.question,
            "book_name": sample.book_name,
            "intent": sample.intent,
            "expected_chunk_ids": sample.expected_chunk_ids,
            "top_chunks": candidates[: max(cutoffs)],
            "retrieval_meta": meta,
            "retrieval_ms": retrieval_ms,
        }
        row["layer1"] = retrieval_metrics(sample, candidates, cutoffs)
        row["layer2"] = context_quality(sample, candidates, args.context_top_k)
        if args.with_generation:
            answer, error = run_answer_generation(sample)
            row["answer_preview"] = answer[:500]
            row["generation_error"] = error
            row["layer3"] = answer_quality(sample, answer, candidates, args.context_top_k) if answer else {}
        else:
            row["layer3"] = {}
            row["generation_error"] = "skipped: pass --with-generation to call the configured LLM"
        rows.append(row)
        by_intent[sample.intent].append(row)
    report = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "golden": str(Path(args.golden).resolve()),
        "elapsed_seconds": round(time.time() - started, 3),
        "config": {
            "context_top_k": args.context_top_k,
            "cutoffs": cutoffs,
            "with_generation": bool(args.with_generation),
        },
        "summary": summarize(rows, cutoffs),
        "by_intent": {intent: summarize(intent_rows, cutoffs) for intent, intent_rows in by_intent.items()},
        "samples": rows,
    }
    write_json(Path(args.output), report)
    return report


def _question_for_role(name: str, role: str) -> tuple[str, str]:
    if role in {"definition", "theorem", "property"}:
        return f"{name}\u662f\u4ec0\u4e48", "definition"
    if role in {"derivation", "proof"}:
        return f"\u5982\u4f55\u63a8\u5bfc{name}", "derivation"
    if role == "example":
        return f"\u4e3e\u4e00\u4e2a{name}\u7684\u4f8b\u9898", "application"
    if role == "algorithm":
        return f"\u600e\u4e48\u7528{name}\u89e3\u9898", "application"
    if role == "formula":
        return f"{name}\u6709\u54ea\u4e9b\u516c\u5f0f", "formula"
    return f"\u8bf7\u89e3\u91ca{name}", "qa"


def bootstrap_golden(args: argparse.Namespace) -> None:
    kg, error = get_safe_kg(args.book_name)
    if error or not getattr(kg, "_is_local", False):
        raise RuntimeError(f"local KG is unavailable for {args.book_name}: {error}")
    preferred_roles = ["definition", "theorem", "property", "derivation", "algorithm", "example", "formula"]
    samples: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for role in preferred_roles:
        for concept in kg.get_concepts_by_role(role):
            name = concept.get("canonical_name", "")
            if not name or (name, role) in seen:
                continue
            detail = kg.get_concept_detail(name) or {}
            occs = [occ for occ in detail.get("occurrences", []) if occ.get("chunk_id") and occ.get("role") == role]
            if not occs:
                occs = [occ for occ in detail.get("occurrences", []) if occ.get("chunk_id")]
            if not occs:
                continue
            occ = occs[0]
            question, intent = _question_for_role(name, role)
            samples.append({
                "question": question,
                "book_name": args.book_name,
                "intent": intent,
                "expected_chunk_ids": [occ["chunk_id"]],
                "expected_chapter": occ.get("section_title", ""),
                "expected_concepts": [name],
                "expected_keywords": [name],
                "reference_answer": "",
            })
            seen.add((name, role))
            if len(samples) >= args.count:
                break
        if len(samples) >= args.count:
            break
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
    print(f"wrote {len(samples)} samples to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate local RAG retrieval/context/answer quality.")
    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("run", help="Run evaluation from a JSONL golden set.")
    run.add_argument("--golden", default=str(DEFAULT_GOLDEN))
    run.add_argument("--output", default=str(DEFAULT_REPORT))
    run.add_argument("--context-top-k", type=int, default=5)
    run.add_argument("--cutoffs", default="1,3,5")
    run.add_argument("--limit", type=int, default=0)
    run.add_argument("--with-generation", action="store_true")
    boot = sub.add_parser("bootstrap", help="Create a starter golden set from the local KG.")
    boot.add_argument("--book-name", default=DEFAULT_BOOK)
    boot.add_argument("--count", type=int, default=40)
    boot.add_argument("--output", default=str(DEFAULT_GOLDEN))
    args = parser.parse_args()
    if args.command == "bootstrap":
        bootstrap_golden(args)
    elif args.command == "run":
        report = run_eval(args)
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        print(f"report: {Path(args.output).resolve()}")
    else:
        parser.print_help()
        raise SystemExit(2)


if __name__ == "__main__":
    main()
