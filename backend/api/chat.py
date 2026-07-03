"""Chat API: SSE streaming and non-streaming dialogue."""
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.conversation_memory import append_message, ensure_conversation_id, get_conversation, list_conversations, load_history, rewrite_followup
from backend.schemas import ChatRequest

router = APIRouter(prefix="/chat", tags=["chat"])
@router.get("/conversations")
def conversations(subject: str = "", book_name: str = "", limit: int = 80):
    return {"success": True, "data": list_conversations(subject=subject, book_name=book_name, limit=limit)}


@router.get("/conversations/{conversation_id}")
def conversation_detail(conversation_id: str):
    conversation_id = ensure_conversation_id(conversation_id)
    return {"success": True, "data": get_conversation(conversation_id)}

@router.post("/log")
def log_conversation_messages(payload: dict):
    conversation_id = ensure_conversation_id(str(payload.get("conversation_id") or ""))
    book_name = str(payload.get("book_name") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    messages = payload.get("messages") or []
    if not isinstance(messages, list):
        return {"success": False, "message": "messages must be a list", "conversation_id": conversation_id}
    appended = 0
    for item in messages[:8]:
        if not isinstance(item, dict):
            continue
        role = "assistant" if item.get("role") == "assistant" else "user"
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        append_message(conversation_id, role, content, book_name=book_name, subject=subject)
        appended += 1
    return {"success": True, "conversation_id": conversation_id, "appended": appended}


@router.post("/stream")
def chat_stream(req: ChatRequest):
    from graph.main_graph import run_graph_stream

    conversation_id = ensure_conversation_id(req.conversation_id)
    history = load_history(conversation_id)
    book_name = (req.book_name or "").strip()
    subject = (req.subject or "").strip()
    use_textbook_context = bool(book_name)
    rewritten_question = rewrite_followup(req.question, history, book_name=book_name, subject=subject)

    def event_generator():
        assistant_chunks: list[str] = []
        assistant_persisted = False
        assistant_persistence_error = ""

        def persist_assistant() -> str:
            nonlocal assistant_persisted, assistant_persistence_error
            if assistant_persisted:
                return assistant_persistence_error

            content = "".join(assistant_chunks)
            if not content.strip():
                assistant_persisted = True
                assistant_persistence_error = ""
                return ""

            try:
                append_message(conversation_id, "assistant", content, book_name=book_name, subject=subject)
                assistant_persisted = True
                assistant_persistence_error = ""
            except Exception as exc:
                assistant_persistence_error = str(exc)
                print(f"[chat] assistant persistence failed: {exc}", flush=True)
            return assistant_persistence_error

        try:
            yield f"data: {json.dumps({'stage': 'context', 'conversation_id': conversation_id, 'rewritten_question': rewritten_question if rewritten_question != req.question else ''}, ensure_ascii=False)}\n\n"
            append_message(conversation_id, "user", req.question, book_name=book_name, subject=subject)
            for event in run_graph_stream(
                user_input=rewritten_question,
                book_name=book_name,
                subject=subject,
                conversation_id=conversation_id,
                target_chapters=req.target_chapters or [],
                use_textbook_context=use_textbook_context,
            ):
                event["conversation_id"] = conversation_id
                if event.get("stage") == "generate":
                    if event.get("replace"):
                        assistant_chunks[:] = [str(event.get("chunk") or "")]
                    elif event.get("chunk"):
                        assistant_chunks.append(str(event.get("chunk")))
                    if event.get("done"):
                        persist_assistant()
                if event.get("stage") == "done":
                    persistence_error = persist_assistant()
                    if persistence_error:
                        event["persistence_error"] = persistence_error
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:
            event = {"stage": "error", "message": str(exc), "done": True, "conversation_id": conversation_id}
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/ask")
def chat_ask(req: ChatRequest):
    from graph.main_graph import run_graph

    conversation_id = ensure_conversation_id(req.conversation_id)
    history = load_history(conversation_id)
    book_name = (req.book_name or "").strip()
    subject = (req.subject or "").strip()
    use_textbook_context = bool(book_name)
    rewritten_question = rewrite_followup(req.question, history, book_name=book_name, subject=subject)
    append_message(conversation_id, "user", req.question, book_name=book_name, subject=subject)

    result = run_graph(
        user_input=rewritten_question,
        book_name=book_name,
        subject=subject,
        conversation_id=conversation_id,
        target_chapters=req.target_chapters or [],
        use_textbook_context=use_textbook_context,
    )
    content = result.get("final_output", "")
    if content.strip():
        append_message(conversation_id, "assistant", content, book_name=book_name, subject=subject)

    return {
        "content": content,
        "intent": result.get("intent", ""),
        "chapters": result.get("target_chapters", []),
        "linked_concepts": result.get("linked_concepts", []),
        "conversation_id": conversation_id,
        "rewritten_question": rewritten_question if rewritten_question != req.question else "",
        "chapter_contents": {k: [d[:200] for d in v[:3]] for k, v in result.get("chapter_contents", {}).items()},
    }
