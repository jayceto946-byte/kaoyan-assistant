"""
Phase 2-5: Concept/Formula Extraction, Occurrence Construction, Concept Merge
从 Phase 1 的 context_packages 构建完整知识图谱。

纯算法处理，不需要 LLM。
"""
import json
import re
import sys
import hashlib
from pathlib import Path
from difflib import SequenceMatcher
from typing import Any

SIMILARITY_THRESHOLD = 0.72  # 字符串相似度阈值，认为同一概念


def normalize_name(name: str) -> str:
    """标准化概念名：去空白、统一括号、去末尾标点。"""
    name = name.strip()
    name = re.sub(r"\s+", "", name)
    name = name.rstrip("，。；：、,.;:")
    # 统一括号
    name = name.replace("（", "(").replace("）", ")")
    name = name.replace("［", "[").replace("］", "]")
    name = name.replace("｛", "{").replace("｝", "}")
    return name


def similarity(a: str, b: str) -> float:
    """计算两个字符串的序列相似度。"""
    return SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()


# ============================================================
# Phase 2: Concept Extraction
# ============================================================

def extract_concepts(context_packages: list[dict]) -> list[dict]:
    """从 context_packages 提取去重概念列表。"""
    # 收集所有 concept_candidates
    raw_names: list[tuple[str, str, str]] = []  # (name, context_id, section_title)
    for cp in context_packages:
        for name in cp.get("concept_candidates", []):
            name = normalize_name(name)
            if name and len(name) >= 2:
                raw_names.append((name, cp.get("context_id", ""), cp.get("section_title", "")))

    # 去重：相似度聚类
    clusters: list[dict] = []  # {canonical: str, aliases: set, sources: list}
    for name, ctx_id, sec_title in raw_names:
        merged = False
        for cluster in clusters:
            if similarity(name, cluster["canonical"]) >= SIMILARITY_THRESHOLD:
                cluster["aliases"].add(name)
                if ctx_id and ctx_id not in [s[1] for s in cluster["sources"]]:
                    cluster["sources"].append((name, ctx_id, sec_title))
                merged = True
                break
        if not merged:
            clusters.append({
                "canonical": name,
                "aliases": {name},
                "sources": [(name, ctx_id, sec_title)],
            })

    # 输出 Concept 对象
    concepts = []
    for i, cluster in enumerate(clusters):
        # 选择 canonical_name：最长的非符号名
        names = sorted(cluster["aliases"], key=lambda n: (-len(n), n))
        canonical = names[0]

        # 构建 source_context
        source_contexts = []
        for alias, ctx_id, sec_title in cluster["sources"]:
            source_contexts.append(f"[{sec_title}] {alias} ({ctx_id})")
        source_context = "; ".join(source_contexts[:5])  # 最多 5 个出处

        concepts.append({
            "concept_id": f"CONCEPT_{i:04d}",
            "canonical_name": canonical,
            "aliases": sorted(cluster["aliases"]),
            "source_context": source_context,
            "confidence": 0.5,  # 后续 Phase 5 调整
        })

    print(f"Phase 2: {len(clusters)} unique concepts from {len(raw_names)} candidates")
    return concepts


# ============================================================
# Phase 3: Formula Extraction
# ============================================================

LATEX_VAR_PATTERN = re.compile(
    r"\\boldsymbol\s*\{([^}]+)\}|\\mathbf\s*\{([^}]+)\}|"
    r"\\mathrm\s*\{([^}]+)\}|\\nabla\s*f\b|"
    r"\\nabla|"
    r"[A-Za-z]\s*\^\s*\{[^}]+\}|[A-Za-z]\s*_\s*\{[^}]+\}|"
    r"[A-Za-z](?=[^a-zA-Z]|$)"
)


def parse_latex_variables(latex: str) -> list[str]:
    """从 LaTeX 公式中提取变量名。"""
    vars_set = set()
    # 简单版本：提取大写/小写字母及带上下标的变量
    for m in LATEX_VAR_PATTERN.finditer(latex):
        var = m.group(0).strip()
        if len(var) <= 20:
            vars_set.add(var)
    return sorted(vars_set)


def extract_formulas(context_packages: list[dict], chunks: list[dict]) -> list[dict]:
    """从 context_packages 和原始 chunks 提取公式对象。"""
    formulas: dict[str, dict] = {}  # LaTeX string -> formula obj

    for cp in context_packages:
        for fl in cp.get("formula_candidates", []):
            fl = fl.strip()
            if not fl or len(fl) < 3:
                continue
            if fl not in formulas:
                formulas[fl] = {
                    "formula_id": "",
                    "formula_latex": fl,
                    "variables": parse_latex_variables(fl),
                    "source_contexts": [],
                }
            formulas[fl]["source_contexts"].append({
                "context_id": cp.get("context_id", ""),
                "section_title": cp.get("section_title", ""),
                "page_idx": cp.get("page_idx", -1),
            })

    # Also extract from chunks' equations field
    chunk_map = {c["chunk_id"]: c for c in chunks}
    for cp in context_packages:
        cid = cp.get("chunk_id", "")
        chunk = chunk_map.get(cid, {})
        for eq in chunk.get("equations", []):
            eq = eq.strip()
            if not eq or len(eq) < 3:
                continue
            if eq not in formulas:
                formulas[eq] = {
                    "formula_id": "",
                    "formula_latex": eq,
                    "variables": parse_latex_variables(eq),
                    "source_contexts": [],
                }
            # avoid duplicate context entries
            ctx_ids = {s["context_id"] for s in formulas[eq]["source_contexts"]}
            if cp.get("context_id") not in ctx_ids:
                formulas[eq]["source_contexts"].append({
                    "context_id": cp.get("context_id", ""),
                    "section_title": cp.get("section_title", ""),
                    "page_idx": cp.get("page_idx", -1),
                })

    # Assign IDs
    result = []
    for i, (latex, obj) in enumerate(formulas.items()):
        obj["formula_id"] = f"FORMULA_{i:04d}"
        result.append(obj)

    print(f"Phase 3: {len(result)} unique formulas")
    return result


# ============================================================
# Phase 4: Occurrence Construction
# ============================================================

CONTENT_TYPE_TO_ROLE: dict[str, str] = {
    "definition": "definition",
    "property": "property",
    "theorem": "theorem",
    "proof": "proof",
    "derivation": "derivation",
    "algorithm": "algorithm",
    "example": "example",
    "exercise": "exercise",
    "explanation": "reference",
    "conclusion": "reference",
    "overview": "reference",
}


def build_occurrences(
    context_packages: list[dict],
    concepts: list[dict],
) -> list[dict]:
    """构建 Occurrence：概念在教材中的每次出现。"""
    # 构建概念名 -> concept_id 的映射
    name_to_cid: dict[str, str] = {}
    for c in concepts:
        for alias in c["aliases"]:
            alias_norm = normalize_name(alias)
            if alias_norm not in name_to_cid:
                name_to_cid[alias_norm] = c["concept_id"]

    occurrences = []
    occ_idx = 0

    for cp in context_packages:
        context_id = cp.get("context_id", "")
        chunk_id = cp.get("chunk_id", "")
        content_type = cp.get("content_type", "explanation")
        role = CONTENT_TYPE_TO_ROLE.get(content_type, "reference")

        for name_raw in cp.get("concept_candidates", []):
            name = normalize_name(name_raw)
            if not name or len(name) < 2:
                continue

            # 模糊匹配到 concept
            concept_id = None
            if name in name_to_cid:
                concept_id = name_to_cid[name]
            else:
                # 尝试相似度匹配
                best_score = 0
                best_cid = None
                for c in concepts:
                    for alias in c["aliases"]:
                        score = similarity(name, alias)
                        if score > best_score and score >= SIMILARITY_THRESHOLD:
                            best_score = score
                            best_cid = c["concept_id"]
                if best_cid:
                    concept_id = best_cid

            if concept_id is None:
                continue

            occ_id = f"OCC_{occ_idx:05d}"
            occ_idx += 1

            occurrences.append({
                "occurrence_id": occ_id,
                "concept_id": concept_id,
                "concept_name": name_raw,
                "context_id": context_id,
                "chunk_id": chunk_id,
                "page_idx": cp.get("page_idx", -1),
                "bbox": cp.get("bbox"),
                "role": role,
                "section_title": cp.get("section_title", ""),
            })

    print(f"Phase 4: {len(occurrences)} occurrences built")
    return occurrences


# ============================================================
# Phase 5: Concept Merge
# ============================================================

def merge_concepts(concepts: list[dict], occurrences: list[dict]) -> list[dict]:
    """合并概念，关联所有 Occurrence。"""
    # 按 concept_id 分组 occurrences
    occ_map: dict[str, list[dict]] = {}
    for occ in occurrences:
        cid = occ["concept_id"]
        occ_map.setdefault(cid, []).append(occ)

    merged = []
    for c in concepts:
        cid = c["concept_id"]
        occs = occ_map.get(cid, [])

        # 计算置信度：出现的次数和角色多样性
        roles = set(o["role"] for o in occs)
        if len(occs) >= 3 and "definition" in roles:
            confidence = 0.9
        elif len(occs) >= 2:
            confidence = 0.7
        elif len(occs) == 1:
            confidence = 0.5
        else:
            confidence = 0.3

        merged.append({
            "concept_id": cid,
            "canonical_name": c["canonical_name"],
            "aliases": c["aliases"],
            "source_context": c["source_context"],
            "confidence": confidence,
            "occurrence_count": len(occs),
            "occurrences": occs,
            "roles": sorted(roles),
        })

    print(f"Phase 5: {len(merged)} concepts merged")
    return merged


# ============================================================
# Main
# ============================================================

def run_phase2_5(
    context_packages_path: str | Path,
    chunks_path: str | Path,
    output_path: str | Path,
):
    context_packages_path = Path(context_packages_path)
    chunks_path = Path(chunks_path)
    output_path = Path(output_path)

    print(f"Loading context packages: {context_packages_path}")
    with open(context_packages_path, "r", encoding="utf-8") as f:
        context_packages = json.load(f)

    print(f"Loading chunks: {chunks_path}")
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"Processing {len(context_packages)} context packages, {len(chunks)} chunks")

    concepts = extract_concepts(context_packages)
    formulas = extract_formulas(context_packages, chunks)
    occurrences = build_occurrences(context_packages, concepts)
    merged_concepts = merge_concepts(concepts, occurrences)

    graph = {
        "meta": {
            "source": str(context_packages_path),
            "total_chunks": len(chunks),
            "total_contexts": len(context_packages),
            "total_concepts": len(merged_concepts),
            "total_formulas": len(formulas),
            "total_occurrences": len(occurrences),
        },
        "concepts": merged_concepts,
        "formulas": formulas,
        "occurrences": occurrences,
        "relations": [],  # Phase 6-7
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)

    print(f"\nOutput: {output_path}")
    print(f"  Concepts: {len(merged_concepts)}")
    print(f"  Formulas: {len(formulas)}")
    print(f"  Occurrences: {len(occurrences)}")
    return graph


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("context_packages_json", help="Path to Phase 1 context_packages JSON")
    ap.add_argument("--chunks", required=True, help="Path to original chunks JSON")
    ap.add_argument("--output", "-o", default=None, help="Output graph JSON path")
    args = ap.parse_args()

    out = args.output or str(Path(args.context_packages_json).with_name(
        Path(args.context_packages_json).stem.replace("_context_packages", "_graph") + ".json"
    ))
    run_phase2_5(args.context_packages_json, args.chunks, out)
