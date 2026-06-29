"""Low-cost exercise candidate analysis.

This module deliberately avoids default LLM calls. It gives fast heuristic labels
for imported exercise candidates so large papers can be reviewed cheaply first.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from typing import Iterable


@dataclass
class ExerciseCandidate:
    id: str
    question_text: str
    answer: str = ""
    explanation: str = ""
    source: str = ""
    subject: str = ""
    chapter: str = ""
    suggested_type: str = ""
    difficulty: int = 3
    tags: list[str] = field(default_factory=list)
    linked_concepts: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    reasons: list[str] = field(default_factory=list)
    needs_llm: bool = False
    needs_review: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


CONCEPT_KEYWORDS: dict[str, list[str]] = {
    "极限": ["极限", "lim", "趋于", "无穷小", "无穷大"],
    "导数": ["导数", "求导", "微分", "derivative", "切线", "法线"],
    "积分": ["积分", "定积分", "不定积分", "原函数", "换元", "分部积分"],
    "矩阵": ["矩阵", "行列式", "特征值", "特征向量", "秩", "逆矩阵"],
    "概率": ["概率", "随机变量", "分布", "期望", "方差", "密度函数"],
    "优化": ["优化", "最优", "目标函数", "约束", "规划", "极值", "拉格朗日"],
    "线性规划": ["线性规划", "单纯形", "可行域", "基变量", "非基变量"],
    "动态规划": ["动态规划", "状态转移", "最优子结构", "阶段", "递推"],
    "图论": ["图", "路径", "最短路", "生成树", "网络", "节点", "边"],
    "排队论": ["排队", "到达率", "服务率", "泊松", "等待时间"],
}

TYPE_RULES: list[tuple[str, list[str]]] = [
    ("判断题", ["判断", "正确", "错误", "对错", "√", "×"]),
    ("证明题", ["证明", "证：", "试证", "show that", "prove"]),
    ("简答题", ["简述", "说明", "解释", "分析", "为什么", "含义"]),
    ("计算题", ["计算", "求", "解", "确定", "最优解", "最小", "最大"]),
]

QUESTION_START_RE = re.compile(r"(?m)^\s*(?:第\s*\d+\s*题|\d+\s*[.、)]|[一二三四五六七八九十]+\s*[、.])\s*")
OPTION_RE = re.compile(r"(?:^|\s)[A-D]\s*[.、)]", re.IGNORECASE)
SUBQUESTION_RE = re.compile(r"(?:\(\s*\d+\s*\)|（\s*\d+\s*）)")
MATH_RE = re.compile(r"(\\frac|\\sum|\\int|\\lim|[=<>≤≥]|\$|\^|_)" )


def split_candidate_text(raw_text: str, limit: int = 200) -> list[str]:
    """Split pasted/imported text into question-like chunks using numbering cues."""
    text = raw_text.replace("\r\n", "\n").strip()
    if not text:
        return []

    starts = [m.start() for m in QUESTION_START_RE.finditer(text)]
    if len(starts) <= 1:
        chunks = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        return chunks[:limit]

    starts.append(len(text))
    chunks: list[str] = []
    for i in range(len(starts) - 1):
        chunk = text[starts[i]:starts[i + 1]].strip()
        if len(chunk) >= 4:
            chunks.append(chunk)
        if len(chunks) >= limit:
            break
    return chunks


def analyze_candidate(
    question_text: str,
    *,
    source: str = "",
    subject: str = "",
    chapter: str = "",
    known_concepts: Iterable[str] | None = None,
) -> ExerciseCandidate:
    text = question_text.strip()
    lowered = text.lower()
    reasons: list[str] = []
    tags: list[str] = []
    linked_concepts: list[dict] = []

    suggested_type = ""
    if len(OPTION_RE.findall(text)) >= 3:
        suggested_type = "选择题"
        reasons.append("检测到 A/B/C/D 选项")
    else:
        for qtype, keywords in TYPE_RULES:
            if any(keyword.lower() in lowered for keyword in keywords):
                suggested_type = qtype
                reasons.append(f"命中题型关键词：{qtype}")
                break
    if not suggested_type:
        suggested_type = "综合题" if len(SUBQUESTION_RE.findall(text)) >= 2 else "未确定"
        if suggested_type == "综合题":
            reasons.append("检测到多个小问")

    concept_scores: dict[str, int] = {}
    for concept, keywords in CONCEPT_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword.lower() in lowered)
        if score:
            concept_scores[concept] = score

    for concept in known_concepts or []:
        clean = concept.strip()
        if clean and clean.lower() in lowered:
            concept_scores[clean] = max(concept_scores.get(clean, 0), 2)

    for concept, score in sorted(concept_scores.items(), key=lambda item: item[1], reverse=True)[:5]:
        tags.append(concept)
        linked_concepts.append({
            "name": concept,
            "confidence": min(0.95, 0.55 + score * 0.12),
            "source": "heuristic",
            "evidence": "题干关键词命中",
        })
    if tags:
        reasons.append("根据题干关键词给出知识点候选")

    difficulty = 2
    if len(text) > 180:
        difficulty += 1
    if len(SUBQUESTION_RE.findall(text)) >= 2:
        difficulty += 1
    if MATH_RE.search(text):
        difficulty += 1
    if any(word in lowered for word in ["证明", "最优", "约束", "特征值", "动态规划"]):
        difficulty += 1
    difficulty = max(1, min(5, difficulty))

    confidence = 0.25
    if suggested_type != "未确定":
        confidence += 0.25
    if tags:
        confidence += min(0.3, 0.12 * len(tags))
    if len(text) >= 30:
        confidence += 0.1
    if chapter:
        confidence += 0.05
    confidence = round(min(0.95, confidence), 2)

    needs_llm = confidence < 0.65 or not tags or suggested_type == "未确定"
    if needs_llm:
        reasons.append("置信度偏低，建议后续批量 LLM 精标或人工确认")
    else:
        reasons.append("规则初判置信度可接受，可人工快速确认")

    return ExerciseCandidate(
        id=str(uuid.uuid4())[:8],
        question_text=text,
        source=source,
        subject=subject,
        chapter=chapter,
        suggested_type=suggested_type,
        difficulty=difficulty,
        tags=tags,
        linked_concepts=linked_concepts,
        confidence=confidence,
        reasons=reasons,
        needs_llm=needs_llm,
    )


def analyze_candidates(
    candidates: Iterable[str],
    *,
    source: str = "",
    subject: str = "",
    chapter: str = "",
    known_concepts: Iterable[str] | None = None,
    limit: int = 200,
) -> list[ExerciseCandidate]:
    results: list[ExerciseCandidate] = []
    for text in candidates:
        if text and text.strip():
            results.append(
                analyze_candidate(
                    text,
                    source=source,
                    subject=subject,
                    chapter=chapter,
                    known_concepts=known_concepts,
                )
            )
        if len(results) >= limit:
            break
    return results