"""
Phase 7: Graph Construction
整合 concepts + formulas + occurrences + relations 为最终知识图谱。
"""
import json
import sys
from pathlib import Path
from collections import defaultdict


def build_knowledge_graph(
    graph_path: str | Path,
    relations_path: str | Path,
    output_path: str | Path,
):
    graph_path = Path(graph_path)
    relations_path = Path(relations_path)
    output_path = Path(output_path)

    print(f"Loading graph: {graph_path}")
    with open(graph_path, "r", encoding="utf-8") as f:
        graph = json.load(f)

    print(f"Loading relations: {relations_path}")
    with open(relations_path, "r", encoding="utf-8") as f:
        relations = json.load(f)

    concepts = graph.get("concepts", [])
    formulas = graph.get("formulas", [])
    occurrences = graph.get("occurrences", [])

    # Build lookup maps
    concept_by_name: dict[str, str] = {}  # normalized name -> concept_id
    for c in concepts:
        for alias in c.get("aliases", []):
            norm = alias.strip().lower()
            if norm not in concept_by_name:
                concept_by_name[norm] = c["concept_id"]

    concept_by_id: dict[str, dict] = {c["concept_id"]: c for c in concepts}

    # Resolve relation source/target to concept_ids
    seen_rels: set[tuple] = set()
    resolved_relations = []
    for r in relations:
        src = r.get("source", "").strip().lower()
        tgt = r.get("target", "").strip().lower()
        src_id = concept_by_name.get(src, src)
        tgt_id = concept_by_name.get(tgt, tgt)
        if src_id in concept_by_id:
            src_id = concept_by_id[src_id]["concept_id"]
        if tgt_id in concept_by_id:
            tgt_id = concept_by_id[tgt_id]["concept_id"]

        rel_key = (src, r["relation"], tgt, r.get("evidence_chunk", ""))
        if rel_key in seen_rels:
            continue
        seen_rels.add(rel_key)
        resolved_relations.append({
            "source_concept": r["source"],
            "source_id": src_id if src_id in concept_by_id else None,
            "relation": r["relation"],
            "target_concept": r["target"],
            "target_id": tgt_id if tgt_id in concept_by_id else None,
            "evidence_chunk": r.get("evidence_chunk", ""),
            "evidence_text": r.get("evidence_text", ""),
            "page_idx": r.get("page_idx", -1),
            "section_title": r.get("section_title", ""),
        })

    # Link formulas to concepts via source_contexts
    concept_by_context: dict[str, str] = {}  # context_id -> concept_id list
    for occ in occurrences:
        ctx = occ.get("context_id", "")
        if ctx not in concept_by_context:
            concept_by_context[ctx] = []
        concept_by_context[ctx].append(occ["concept_id"])

    for fm in formulas:
        related = set()
        for sc in fm.get("source_contexts", []):
            ctx = sc.get("context_id", "")
            if ctx in concept_by_context:
                related.update(concept_by_context[ctx])
        fm["related_concepts"] = sorted(related)

    # Stats
    resolved_count = sum(1 for r in resolved_relations
                         if r["source_id"] and r["target_id"])
    relation_stats = defaultdict(int)
    for r in resolved_relations:
        relation_stats[r["relation"]] += 1

    # Final graph
    final_graph = {
        "meta": {
            **graph["meta"],
            "total_relations": len(resolved_relations),
            "relations_resolved": resolved_count,
            "relation_distribution": dict(relation_stats),
        },
        "concepts": concepts,
        "formulas": formulas,
        "occurrences": occurrences,
        "relations": resolved_relations,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_graph, f, ensure_ascii=False, indent=2)

    print(f"\nPhase 7 done. Output: {output_path}")
    print(f"  Concepts:       {len(concepts)}")
    print(f"  Formulas:       {len(formulas)}")
    print(f"  Occurrences:    {len(occurrences)}")
    print(f"  Relations:      {len(resolved_relations)} ({resolved_count} resolved to concept IDs)")
    print(f"  Relation types: {dict(relation_stats)}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("graph_json", help="Phase 2-5 graph JSON")
    ap.add_argument("relations_json", help="Phase 6 relations JSON")
    ap.add_argument("--output", "-o", default=None)
    args = ap.parse_args()

    out = args.output or str(Path(args.graph_json).with_name(
        Path(args.graph_json).stem.replace("_graph", "_knowledge_graph") + ".json"
    ))
    build_knowledge_graph(args.graph_json, args.relations_json, out)
