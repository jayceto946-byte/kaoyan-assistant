"""
Phase 1: Context Package Construction
从 chunks.json 生成 Context Package，使用 LLM 做 content_type 分类、
摘要生成、概念候选抽取。
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

BATCH_SIZE = 10
MAX_RETRIES = 3
TEMPERATURE = 0.3

ALLOWED_CONTENT_TYPES = [
    "definition", "property", "theorem", "proof", "derivation",
    "algorithm", "example", "exercise", "figure_description",
    "table_description", "explanation", "conclusion",
    "front_matter",   # 扉页、前言、目录等
    "overview",        # 章节概述
]

SYSTEM_PROMPT = """你是一个理工科教材知识图谱构建专家。你的任务是对教材文本块进行分类和元信息抽取。

## 严格规则
1. 不允许脱离原文生成知识
2. 所有抽取必须基于给定的文本，不得凭常识补充
3. concept_candidates 只能从原文中出现的术语/概念中提取
4. 遇到不确定的情况，confidence 设为 low

## content_type 分类标准
- definition: 对某个概念给出明确定义
- property: 描述某个概念的数学/物理性质
- theorem: 陈述定理、引理、推论
- proof: 对定理的证明过程
- derivation: 数学公式推导过程
- algorithm: 算法步骤、计算流程、伪代码
- example: 例题、实例讲解
- exercise: 习题
- figure_description: 描述或解释图表
- table_description: 描述或解释表格
- explanation: 一般性解释说明文字
- conclusion: 章节总结、小结
- front_matter: 扉页、版权页、前言、目录
- overview: 章节内容概述、学习目标

## 输出格式
对每个文本块输出一个 JSON 对象，包含以下字段：
- context_id: "ctx_<原chunk_id>"
- chunk_id: 原 chunk_id
- section_title: 原 section_title
- summary: 用 1-2 句中文概括本段核心知识
- content_type: 从上述类型中选择一个最匹配的
- concept_candidates: 文本中出现的学科概念术语列表（中文优先）
- symbol_candidates: 文本中出现的数学符号列表（如 A^(k), ∇f, S^(k)）
- formula_candidates: 文本中出现的编号公式列表（如 (4-40), (4-41)）
- confidence: high / medium / low

所有字段必须填写，没有内容时用空列表 []。"""


def build_user_prompt(chunks: list[dict]) -> str:
    """构建包含多个 chunk 的用户消息。"""
    lines = ["请分析以下文本块，对每个块输出一个 JSON 对象，放在 JSON 数组中返回。\n"]
    for i, c in enumerate(chunks):
        st = c.get("section_title", "(no title)")
        eqs = c.get("equations", [])
        eq_str = ", ".join(eqs) if eqs else "无"
        lines.append(
            f"--- 块 {i} ---\n"
            f"chunk_id: {c['chunk_id']}\n"
            f"section_title: {st}\n"
            f"page_idx: {c.get('page_idx', -1)}\n"
            f"type_sequence: {c.get('type_sequence', [])}\n"
            f"equations: {eq_str}\n"
            f"text:\n{c['text']}\n"
        )
    lines.append("\n请以 JSON 数组格式返回，数组元素顺序与上述块顺序一致。")
    return "\n".join(lines)


def parse_response(text: str, expected_count: int) -> list[dict] | None:
    """从 LLM 响应中解析 JSON 数组。"""
    # 尝试直接解析
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 代码块
    import re
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    # 尝试找到最外层的 [ ... ]
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    return None


def run_phase1(
    chunks_path: str | Path,
    output_path: str | Path,
    resume: bool = True,
):
    """Phase 1 主流程。"""
    chunks_path = Path(chunks_path)
    output_path = Path(output_path)

    with open(chunks_path, "r", encoding="utf-8") as f:
        all_chunks: list[dict] = json.load(f)

    # 预处理：为 (no title) 的 chunk 继承最近的有效 section_title
    last_title = "root"
    for c in all_chunks:
        if c.get("section_title") != "(no title)":
            last_title = c["section_title"]
        else:
            c["_inherited_title"] = last_title

    # 加载已有进度
    results: dict[str, dict] = {}
    if resume and output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
            if isinstance(existing, list):
                for item in existing:
                    results[item.get("chunk_id", "")] = item
                print(f"Resumed {len(results)} already-processed chunks")

    # 找出未处理的 chunk
    pending = [c for c in all_chunks if c["chunk_id"] not in results]
    total = len(pending)
    if total == 0:
        print("All chunks already processed in Phase 1.")
        return

    print(f"Phase 1: {total} chunks pending, batch_size={BATCH_SIZE}")

    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured. Set it in .env before running this script.")
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_API_BASE)

    for batch_start in range(0, total, BATCH_SIZE):
        batch = pending[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        print(f"\nBatch {batch_num} ({batch_start+1}-{min(batch_start+BATCH_SIZE, total)}/{total}) ...")

        user_prompt = build_user_prompt(batch)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = client.chat.completions.create(
                    model=DEEPSEEK_MODEL,
                    temperature=TEMPERATURE,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    timeout=120,
                )
                raw = resp.choices[0].message.content or ""
                parsed = parse_response(raw, len(batch))

                if parsed is None or len(parsed) != len(batch):
                    print(f"  Attempt {attempt}: parse failed (got {len(parsed) if parsed else 0} items, expected {len(batch)})")
                    # 输出原始响应用于调试
                    if parsed and len(parsed) < len(batch):
                        print(f"  Partial response, accepting {len(parsed)} items")
                        # Fill in partial results
                        for j, cp in enumerate(parsed):
                            if j < len(batch):
                                results[batch[j]["chunk_id"]] = cp
                    if attempt < MAX_RETRIES:
                        time.sleep(2 * attempt)
                    continue

                for j, cp in enumerate(parsed):
                    # Ensure required fields
                    cp.setdefault("context_id", f"ctx_{batch[j]['chunk_id']}")
                    cp.setdefault("chunk_id", batch[j]["chunk_id"])
                    cp.setdefault("section_title", batch[j].get("section_title", ""))
                    cp.setdefault("content_type", "explanation")
                    cp.setdefault("concept_candidates", [])
                    cp.setdefault("symbol_candidates", [])
                    cp.setdefault("formula_candidates", [])
                    cp.setdefault("confidence", "medium")
                    cp["page_idx"] = batch[j].get("page_idx", -1)
                    cp["bbox"] = batch[j].get("bbox")
                    results[batch[j]["chunk_id"]] = cp

                print(f"  OK ({len(parsed)} items)")
                break

            except Exception as e:
                print(f"  Attempt {attempt}: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(3 * attempt)
                else:
                    # 失败时写入占位
                    for c in batch:
                        results[c["chunk_id"]] = {
                            "context_id": f"ctx_{c['chunk_id']}",
                            "chunk_id": c["chunk_id"],
                            "section_title": c.get("section_title", ""),
                            "summary": "",
                            "content_type": "explanation",
                            "concept_candidates": [],
                            "symbol_candidates": [],
                            "formula_candidates": [],
                            "confidence": "low",
                            "page_idx": c.get("page_idx", -1),
                            "bbox": c.get("bbox"),
                            "_error": str(e),
                        }
                    print(f"  FAILED, wrote placeholders")

        # 每批后保存（只保存已处理完的）
        ordered = [results[c["chunk_id"]] for c in all_chunks if c["chunk_id"] in results]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ordered, f, ensure_ascii=False, indent=2)

        # API 调用间隔
        time.sleep(1.5)

    print(f"\nPhase 1 done. Output: {output_path}")
    return results


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("chunks_json", help="Path to chunks JSON file")
    ap.add_argument("--output", "-o", default=None, help="Output JSON path")
    ap.add_argument("--no-resume", action="store_true", help="Don't resume from existing output")
    args = ap.parse_args()

    output = args.output or str(Path(args.chunks_json).with_name(
        Path(args.chunks_json).stem.replace("_middle_chunks", "_context_packages") + ".json"
    ))

    run_phase1(args.chunks_json, output, resume=not args.no_resume)
