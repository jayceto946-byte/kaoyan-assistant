"""
Phase 6: Relation Extraction
从 Context Package 中抽取概念间关系，使用 LLM。
"""
import json
import os
import time
from pathlib import Path
from typing import Any

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_KG_MODEL") or os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-chat")

BATCH_SIZE = 8
MAX_RETRIES = 3
TEMPERATURE = 0.2

ALLOWED_RELATIONS = [
    "defines", "depends_on", "uses", "derives_from",
    "satisfies", "contains", "references", "illustrates",
]

SYSTEM_PROMPT = """你是一个理工科教材知识图谱关系抽取专家。

## 任务
给定一段教材文本块及其概念列表，找出概念之间在本文本块中**有明确证据**的关系。

## 关系类型（只能选用以下关系）
- defines: A 定义了 B（给出定义）
- depends_on: A 依赖于 B（逻辑/数学依赖）
- uses: A 使用/应用 B
- derives_from: A 从 B 推导而来
- satisfies: A 满足 B（条件/约束满足）
- contains: A 包含 B（组成/子类关系）
- references: A 引用 B（提及/参考）
- illustrates: A 举例说明 B

## 严格规则
1. 关系必须**严格基于给定的文本块**，不得凭常识补充
2. source 和 target 必须是概念列表中的概念
3. 每个关系都要能追溯到原文中的具体句子
4. 如果本文本块中没有明确的概念间关系，返回空列表
5. 不要编造不存在的关系

## 输出格式
对每个文本块返回一个 relation 的 JSON 数组：
[{"source": "概念A", "relation": "defines", "target": "概念B", "evidence": "原文中证明该关系的句子片段"}]

所有字段必须填写。如果没有关系，返回空数组 []。"""


def build_prompt(batch: list[dict]) -> str:
    lines = ["请分析以下文本块，找出每个块中概念间的关系。\n"]
    for i, cp in enumerate(batch):
        concepts = cp.get("concept_candidates", [])
        lines.append(
            f"--- 块 {i} (chunk_id: {cp['chunk_id']}) ---\n"
            f"content_type: {cp.get('content_type', '')}\n"
            f"summary: {cp.get('summary', '')}\n"
            f"concepts: {json.dumps(concepts, ensure_ascii=False)}\n"
            f"text:\n{cp.get('text', '')[:2000]}\n"
        )
    lines.append("\n请以 JSON 数组的数组返回：[[块0的关系],[块1的关系],...]，顺序与上面一致。")
    return "\n".join(lines)


def parse_response(text: str, count: int) -> list[list[dict]] | None:
    """解析 LLM 响应为 list[list[dict]]。"""
    import re
    for pattern in [
        text,
        *(re.findall(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL) or []),
    ]:
        try:
            data = json.loads(pattern)
            if isinstance(data, list) and len(data) == count:
                if all(isinstance(x, list) for x in data):
                    return data
        except (json.JSONDecodeError, TypeError):
            continue
    # Try to find any JSON array
    start = text.find("[[")
    end = text.rfind("]]") + 2
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end])
            if isinstance(data, list) and len(data) == count:
                return data
        except json.JSONDecodeError:
            pass
    return None


def run_phase6(
    context_packages_path: str | Path,
    output_path: str | Path,
    resume: bool = True,
):
    context_packages_path = Path(context_packages_path)
    output_path = Path(output_path)

    with open(context_packages_path, "r", encoding="utf-8") as f:
        all_cps: list[dict] = json.load(f)

    total = len(all_cps)
    print(f"Phase 6: {total} context packages, batch_size={BATCH_SIZE}")

    # Load existing results
    all_relations: list[dict] = []
    processed_ids: set[str] = set()
    if resume and output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
            if isinstance(existing, list):
                all_relations = existing
                for r in existing:
                    processed_ids.add(r.get("evidence_chunk", ""))
                print(f"Resumed {len(all_relations)} relations from {len(processed_ids)} chunks")

    # Filter pending chunks - skip chunks with no concept candidates
    pending = [c for c in all_cps
               if c["chunk_id"] not in processed_ids
               and len(c.get("concept_candidates", [])) >= 2]
    print(f"Pending: {len(pending)} chunks (with >=2 concepts)")

    if not pending:
        print("No pending chunks with sufficient concepts.")
        return

    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured. Set it in .env before running this script.")
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_API_BASE)

    for batch_start in range(0, len(pending), BATCH_SIZE):
        batch = pending[batch_start:batch_start + BATCH_SIZE]
        bnum = batch_start // BATCH_SIZE + 1
        total_batches = (len(pending) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"\nBatch {bnum}/{total_batches} ({batch_start+1}-{min(batch_start+BATCH_SIZE,len(pending))}/{len(pending)}) ...")

        prompt = build_prompt(batch)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = client.chat.completions.create(
                    model=DEEPSEEK_MODEL,
                    temperature=TEMPERATURE,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    timeout=120,
                )
                raw = resp.choices[0].message.content or ""
                parsed = parse_response(raw, len(batch))

                if parsed is None:
                    print(f"  Attempt {attempt}: parse failed")
                    if attempt < MAX_RETRIES:
                        time.sleep(2 * attempt)
                    continue

                new_count = 0
                for j, rels in enumerate(parsed):
                    if not isinstance(rels, list):
                        continue
                    cp = batch[j]
                    for rel in rels:
                        if not isinstance(rel, dict):
                            continue
                        src = rel.get("source", "")
                        tgt = rel.get("target", "")
                        rt = rel.get("relation", "")
                        if rt not in ALLOWED_RELATIONS:
                            continue
                        if not src or not tgt:
                            continue
                        all_relations.append({
                            "source": src,
                            "relation": rt,
                            "target": tgt,
                            "evidence_chunk": cp["chunk_id"],
                            "evidence_text": rel.get("evidence", ""),
                            "page_idx": cp.get("page_idx", -1),
                            "section_title": cp.get("section_title", ""),
                            "context_id": cp.get("context_id", ""),
                        })
                        new_count += 1

                print(f"  OK: +{new_count} relations (total: {len(all_relations)})")
                break

            except Exception as e:
                print(f"  Attempt {attempt}: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(3 * attempt)
                else:
                    print(f"  FAILED for this batch")

        # Save incrementally
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_relations, f, ensure_ascii=False, indent=2)

        time.sleep(1.0)

    print(f"\nPhase 6 done. {len(all_relations)} relations total.")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("context_packages_json")
    ap.add_argument("--output", "-o", default=None)
    ap.add_argument("--no-resume", action="store_true")
    args = ap.parse_args()

    out = args.output or str(Path(args.context_packages_json).with_name(
        Path(args.context_packages_json).stem.replace("_context_packages", "_relations") + ".json"
    ))
    run_phase6(args.context_packages_json, out, resume=not args.no_resume)
