"""Evaluate RAG retrieval reports with the external ir_measures library."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_DEPS = ROOT / ".eval_deps" / "ir_measures"
if EXTERNAL_DEPS.exists():
    sys.path.insert(0, str(EXTERNAL_DEPS))

try:
    import ir_measures
    from ir_measures import MRR, Qrel, Recall, ScoredDoc, nDCG
except ImportError as exc:  # pragma: no cover - exercised manually when dep is absent.
    raise SystemExit(
        "ir_measures is not installed. Install it with:\n"
        "  .\\venv310\\Scripts\\python.exe -m pip install ir_measures "
        "-t .\\.eval_deps\\ir_measures --no-warn-script-location"
    ) from exc


def _load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_ranked_chunks(sample: dict[str, Any]) -> list[dict[str, Any]]:
    chunks = sample.get("top_chunks") or []
    return [chunk for chunk in chunks if chunk.get("chunk_id")]


def build_ir_inputs(report: dict[str, Any]) -> tuple[list[Qrel], list[ScoredDoc], dict[str, Any]]:
    qrels: list[Qrel] = []
    run: list[ScoredDoc] = []
    skipped_without_qrels = 0
    skipped_without_run = 0

    for sample in report.get("samples", []):
        qid = str(sample.get("index"))
        expected_ids = [str(chunk_id) for chunk_id in sample.get("expected_chunk_ids") or [] if chunk_id]
        if not expected_ids:
            skipped_without_qrels += 1
            continue

        for chunk_id in expected_ids:
            qrels.append(Qrel(qid, chunk_id, 1))

        chunks = _iter_ranked_chunks(sample)
        if not chunks:
            skipped_without_run += 1
            continue
        for rank, chunk in enumerate(chunks, 1):
            score = float(len(chunks) - rank + 1)
            run.append(ScoredDoc(qid, str(chunk["chunk_id"]), score))

    meta = {
        "queries_with_qrels": len({q.query_id for q in qrels}),
        "qrels": len(qrels),
        "run_docs": len(run),
        "skipped_without_qrels": skipped_without_qrels,
        "skipped_without_run": skipped_without_run,
    }
    return qrels, run, meta


def evaluate(report_path: Path, output_path: Path | None = None) -> dict[str, Any]:
    report = _load_report(report_path)
    qrels, run, meta = build_ir_inputs(report)
    measures = [
        Recall @ 1,
        Recall @ 3,
        Recall @ 5,
        Recall @ 10,
        MRR @ 10,
        nDCG @ 3,
        nDCG @ 5,
        nDCG @ 10,
    ]
    scores = ir_measures.calc_aggregate(measures, qrels, run)
    result = {
        "source_report": str(report_path.resolve()),
        "library": "ir_measures",
        "library_metrics": {str(measure): value for measure, value in scores.items()},
        "input_meta": meta,
    }
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-check RAG retrieval with ir_measures.")
    parser.add_argument(
        "--report",
        default=str(ROOT / "data" / "eval" / "rag_eval_report_40_top_level.json"),
        help="Report JSON produced by scripts/evaluate_rag.py run.",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "data" / "eval" / "rag_eval_ir_measures_report.json"),
        help="Output JSON path for ir_measures scores.",
    )
    args = parser.parse_args()
    result = evaluate(Path(args.report), Path(args.output))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"report: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
