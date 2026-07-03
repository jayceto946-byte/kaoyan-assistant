"""Controlled read-only agent API.

This is the first step toward tool calling: the backend chooses from a small
Tool Registry, executes only read-only/proposal tools, and returns evidence.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.tools.learning_tools import summarize_learning_evidence
from backend.tools.registry import ToolContext, get_tool_registry
from utils.thinking_filter import strip_thinking

router = APIRouter(prefix="/agent", tags=["controlled-agent"])


class ToolCallRequest(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    book_name: str = ""
    subject: str = ""
    conversation_id: str = ""
    allow_write: bool = False


class ReadOnlyAgentRequest(BaseModel):
    question: str
    book_name: str = ""
    subject: str = ""
    conversation_id: str = ""
    synthesize: bool = True
    max_tools: int = Field(default=6, ge=1, le=10)


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term.lower() in text for term in terms)


def _select_tool_calls(req: ReadOnlyAgentRequest) -> list[dict]:
    question = req.question.strip()
    lowered = question.lower()
    calls: list[dict] = []

    review_terms = ["复习", "到期", "薄弱", "弱点", "错题", "错因", "掌握", "review", "mistake", "weak"]
    add_terms = ["加入错题", "添加错题", "记到错题", "收进错题", "add mistake"]
    concept_terms = ["概念", "公式", "定义", "定理", "知识点", "concept", "formula"]

    if req.book_name and _contains_any(lowered, review_terms):
        calls.append({"tool": "build_review_plan", "args": {"limit": 8}})
        calls.append({"tool": "get_due_mistakes", "args": {"limit": 8}})
        calls.append({"tool": "get_mistake_stats", "args": {"limit": 8}})

    if req.book_name and _contains_any(lowered, concept_terms):
        calls.append({"tool": "search_concepts", "args": {"query": question, "limit": 5}})

    if req.book_name:
        calls.append({"tool": "search_textbook", "args": {"query": question, "limit": 5}})
        if not any(call["tool"] == "search_concepts" for call in calls):
            calls.append({"tool": "search_concepts", "args": {"query": question, "limit": 3}})

    if _contains_any(lowered, add_terms):
        calls.append({"tool": "propose_add_mistake", "args": {"question_text": question, "subject": req.subject}})

    if not calls and req.book_name:
        calls.append({"tool": "search_textbook", "args": {"query": question, "limit": 5}})

    deduped = []
    seen = set()
    for call in calls:
        key = (call["tool"], json.dumps(call["args"], ensure_ascii=False, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(call)
        if len(deduped) >= req.max_tools:
            break
    return deduped


def _compact_tool_outputs(outputs: list[dict]) -> str:
    compact = []
    for item in outputs:
        result = item.get("result", {})
        data = result.get("data")
        if isinstance(data, dict) and "snippets" in data:
            data = {
                "book_name": data.get("book_name"),
                "snippets": [
                    {
                        "chapter": s.get("chapter"),
                        "chunk_id": s.get("chunk_id"),
                        "role": s.get("role"),
                        "text": str(s.get("text") or "")[:500],
                    }
                    for s in data.get("snippets", [])[:4]
                ],
            }
        compact.append({
            "tool": item.get("tool"),
            "success": result.get("success"),
            "message": result.get("message"),
            "data": data,
            "pending_action": result.get("pending_action"),
        })
    return json.dumps(compact, ensure_ascii=False, indent=2)


def _synthesize_answer(req: ReadOnlyAgentRequest, outputs: list[dict], summary: dict) -> str:
    from config import get_llm

    prompt = f"""You are a controlled study assistant for postgraduate exam preparation.
Answer in Chinese using only the tool evidence below. If evidence is missing, say what is missing and give a cautious next step.
Do not claim that any pending action has been executed.

Question:
{req.question}

Context:
- book_name: {req.book_name or "(none)"}
- subject: {req.subject or "(none)"}

Tool evidence:
{_compact_tool_outputs(outputs)}

Evidence summary:
{json.dumps(summary, ensure_ascii=False)}

Requirements:
1. Keep the answer concise and actionable.
2. Mention textbook evidence, due reviews, weak points, or pending confirmations only when they appear in the tool evidence.
3. For review plans, give the next 3-5 actions.
4. Do not output thinking.
"""
    try:
        content = get_llm(temperature=0.3).invoke(prompt).content
        return strip_thinking(content).strip()
    except Exception as exc:
        return f"工具调用已完成，但生成总结失败：{exc}"


@router.get("/tools")
def list_agent_tools(include_write: bool = False):
    registry = get_tool_registry()
    return {"success": True, "data": registry.list_tools(include_write=include_write)}


@router.post("/tools/call")
def call_agent_tool(req: ToolCallRequest):
    registry = get_tool_registry()
    context = ToolContext(book_name=req.book_name, subject=req.subject, conversation_id=req.conversation_id)
    result = registry.call(req.tool, req.args, context, allow_write=req.allow_write)
    return {"success": result.success, "tool": req.tool, "result": result.to_dict()}


@router.post("/read-only")
def run_read_only_agent(req: ReadOnlyAgentRequest):
    registry = get_tool_registry()
    context = ToolContext(book_name=req.book_name, subject=req.subject, conversation_id=req.conversation_id)
    selected = _select_tool_calls(req)

    outputs = []
    for call in selected:
        result = registry.call(call["tool"], call.get("args", {}), context, allow_write=False)
        outputs.append({
            "tool": call["tool"],
            "args": call.get("args", {}),
            "result": result.to_dict(),
        })

    summary = summarize_learning_evidence(outputs)
    answer = _synthesize_answer(req, outputs, summary) if req.synthesize else ""
    return {
        "success": True,
        "mode": "read_only",
        "answer": answer,
        "selected_tools": selected,
        "tool_outputs": outputs,
        "summary": summary,
    }
