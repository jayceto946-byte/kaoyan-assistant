"""Exercises API: general question bank CRUD and mistake import."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile

from backend.schemas import (
    ExerciseAddRequest,
    ExerciseAnalyzeRequest,
    ExerciseBatchAddRequest,
    ExerciseCandidateOut,
    ExerciseFromMistakeRequest,
    ExerciseListRequest,
    ExercisePracticeRequest,
    ExerciseToMistakeRequest,
    ExerciseRecordOut,
    ExerciseStatusRequest,
)
from config import DATA_DIR, PROGRESS_PATH
from memory.exercise_bank import ExerciseRecord, get_exercise_bank
from memory.exercise_file_importer import extract_exercise_text
from memory.exercise_importer import analyze_candidates, refine_low_confidence_candidates, split_candidate_blocks
from memory.mistake_book import MistakeRecord, get_mistake_book
from memory.learning_events import LearningEvent, concept_names, get_learning_event_store
from utils.latex_sanitizer import sanitize_latex
from utils.subject_catalog import normalize_subject_value
from utils.thinking_filter import strip_thinking

router = APIRouter(prefix="/exercises", tags=["exercises"])
UPLOAD_DIR = DATA_DIR / "uploads" / "exercises"


def _log_learning_event(event_type: str, *, book_name: str = "default", record: ExerciseRecord | None = None, source_type: str = "exercise", source_id: str = "", payload: dict | None = None) -> None:
    try:
        get_learning_event_store().append(LearningEvent(
            event_type=event_type,
            book_name=book_name,
            subject=record.subject if record else "",
            source_type=source_type,
            source_id=source_id or (record.id if record else ""),
            concept_names=concept_names(record.linked_concepts if record else []),
            payload=payload or {},
        ))
    except Exception as exc:
        print(f"[LearningEvent] exercise event failed: {exc}", flush=True)


def _safe_upload_name(filename: str) -> str:
    raw = Path(filename or "exercise_import").name
    stem = re.sub(r"[^\w\-.\u4e00-\u9fff]+", "_", Path(raw).stem).strip("._") or "exercise_import"
    suffix = Path(raw).suffix.lower()
    return f"{stem[:80]}{suffix}"


def _save_upload(file: UploadFile) -> Path:
    if not file.filename:
        raise ValueError("请选择要上传的文件")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".docx", ".pdf"}:
        raise ValueError("仅支持 .docx 和 .pdf 文件")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / _safe_upload_name(file.filename)
    base = dest.with_suffix("")
    suffix = dest.suffix
    counter = 1
    while dest.exists():
        dest = Path(f"{base}_{counter}{suffix}")
        counter += 1
    with open(dest, "wb") as fh:
        shutil.copyfileobj(file.file, fh)
    return dest


def _bank(book_name: str = "default"):
    return get_exercise_bank(book_name, str(PROGRESS_PATH))


def _tags_from_text(tags: str) -> list[str]:
    return [item.strip() for item in tags.split(",") if item.strip()]


def _record_to_out(record: ExerciseRecord) -> ExerciseRecordOut:
    return ExerciseRecordOut(**record.to_dict())



def _candidate_to_add_payload(candidate) -> ExerciseAddRequest:
    return ExerciseAddRequest(
        question_text=candidate.question_text,
        answer=candidate.answer,
        explanation=candidate.explanation,
        source=candidate.source,
        subject=candidate.subject,
        chapter=candidate.chapter,
        tags=", ".join(candidate.tags),
        question_type=candidate.suggested_type,
        difficulty=candidate.difficulty,
        linked_concepts=candidate.linked_concepts,
        origin_type="import_candidate",
        origin_id=candidate.id,
        status="needs_review" if candidate.needs_review else "new",
        notes="; ".join(candidate.reasons),
    )


def _mistake_from_exercise(record: ExerciseRecord, user_answer: str = "", mistake_type: list[str] | None = None) -> MistakeRecord:
    return MistakeRecord(
        question_text=record.question_text,
        user_answer=user_answer.strip(),
        correct_answer=record.answer,
        source=record.source,
        subject=record.subject,
        chapter=record.chapter,
        tags=record.tags,
        mistake_type=mistake_type or ["思路卡住"],
        difficulty=record.difficulty,
        image_path=record.image_path,
        ocr_text=record.ocr_text,
        explanation=record.explanation,
        linked_concepts=record.linked_concepts,
        notes=f"由习题库转入：{record.id}",
    )


def _record_from_request(req: ExerciseAddRequest, book_name: str = "default") -> ExerciseRecord:
    return ExerciseRecord(
        question_text=req.question_text.strip(),
        answer=req.answer.strip(),
        explanation=sanitize_latex(strip_thinking(req.explanation.strip())) if req.explanation.strip() else "",
        source=req.source.strip(),
        subject=normalize_subject_value(req.subject, fallback=book_name),
        chapter=req.chapter.strip() or None,
        tags=_tags_from_text(req.tags),
        question_type=req.question_type.strip(),
        difficulty=max(1, min(5, int(req.difficulty or 3))),
        image_path=req.image_path,
        ocr_text=req.ocr_text.strip(),
        linked_concepts=req.linked_concepts,
        origin_type=req.origin_type.strip() or "manual",
        origin_id=req.origin_id.strip(),
        status=req.status.strip() or "new",
        notes=req.notes.strip(),
    )


@router.post("/add")
def add_exercise(req: ExerciseAddRequest, book_name: str = "default"):
    if not req.question_text.strip():
        return {"success": False, "message": "题干不能为空"}
    try:
        record = _record_from_request(req, book_name=book_name)
        rid = _bank(book_name).add(record)
        _log_learning_event("exercise_added", book_name=book_name, record=record, payload={"origin_type": record.origin_type, "status": record.status})
        return {"success": True, "id": rid, "data": _record_to_out(record), "message": "已保存到习题库"}
    except Exception as e:
        return {"success": False, "message": f"保存失败：{e}"}


@router.post("/list")
def list_exercises(req: ExerciseListRequest, book_name: str = "default"):
    records = _bank(book_name).list_all(
        subject=req.subject or None,
        chapter=req.chapter or None,
        tag=req.tag or None,
        search_kw=req.search_kw,
        status=req.status,
        limit=req.limit,
    )
    return {"success": True, "data": [_record_to_out(r) for r in records]}


@router.get("/stats")
def get_exercise_stats(book_name: str = "default", subject: str = ""):
    return {"success": True, "data": _bank(book_name).stats(subject=subject or None)}






@router.post("/upload-analyze")
def upload_and_analyze_exercises(
    file: UploadFile = File(...),
    source: str = Form(""),
    subject: str = Form(""),
    chapter: str = Form(""),
    limit: int = Form(200),
    use_llm: bool = Form(False),
    llm_max_items: int = Form(20),
    book_name: str = "default",
):
    try:
        saved_path = _save_upload(file)
        extracted = extract_exercise_text(saved_path)
        if not extracted.text.strip():
            return {
                "success": False,
                "message": "未提取到可切分文本。若这是扫描 PDF，需要先接入 OCR。",
                "file": str(saved_path),
                "extract": extracted.to_dict(),
            }
        effective_source = source.strip() or saved_path.name
        effective_subject = normalize_subject_value(subject, fallback=book_name)
        candidates = analyze_candidates(
            split_candidate_blocks(extracted.text, limit=limit),
            source=effective_source,
            subject=effective_subject,
            chapter=chapter.strip(),
            limit=limit,
        )
        if use_llm:
            candidates = refine_low_confidence_candidates(candidates, max_items=llm_max_items)
        data = [ExerciseCandidateOut(**candidate.to_dict()) for candidate in candidates]
        needs_llm_count = sum(1 for candidate in candidates if candidate.needs_llm)
        llm_refined_count = sum(1 for candidate in candidates if candidate.refined_by_llm)
        return {
            "success": True,
            "message": f"已从文件解析出 {len(data)} 道候选题",
            "data": data,
            "summary": {
                "total": len(data),
                "needs_llm": needs_llm_count,
                "auto_confident": len(data) - needs_llm_count,
                "llm_refined": llm_refined_count,
            },
            "file": str(saved_path),
            "extract": extracted.to_dict(),
        }
    except Exception as exc:
        return {"success": False, "message": f"文件导入失败：{exc}"}

@router.post("/analyze-candidates")
def analyze_exercise_candidates(req: ExerciseAnalyzeRequest, book_name: str = "default"):
    source = req.source.strip()
    subject = normalize_subject_value(req.subject, fallback=book_name)
    chapter = req.chapter.strip()
    raw_candidates = req.candidates or split_candidate_blocks(req.raw_text, limit=req.limit)
    candidates = analyze_candidates(
        raw_candidates,
        source=source,
        subject=subject,
        chapter=chapter,
        known_concepts=req.known_concepts,
        limit=req.limit,
    )
    if req.use_llm:
        candidates = refine_low_confidence_candidates(
            candidates,
            known_concepts=req.known_concepts,
            max_items=req.llm_max_items,
        )
    data = [ExerciseCandidateOut(**candidate.to_dict()) for candidate in candidates]
    needs_llm_count = sum(1 for candidate in candidates if candidate.needs_llm)
    llm_refined_count = sum(1 for candidate in candidates if candidate.refined_by_llm)
    return {
        "success": True,
        "data": data,
        "summary": {
            "total": len(data),
            "needs_llm": needs_llm_count,
            "auto_confident": len(data) - needs_llm_count,
            "llm_refined": llm_refined_count,
        },
    }


@router.post("/batch-add")
def batch_add_exercises(req: ExerciseBatchAddRequest, book_name: str = "default"):
    bank = _bank(book_name)
    saved = []
    for item in req.exercises:
        if not item.question_text.strip():
            continue
        record = _record_from_request(item, book_name=book_name)
        bank.add(record)
        _log_learning_event("exercise_imported", book_name=book_name, record=record, payload={"origin_type": record.origin_type, "status": record.status})
        saved.append(_record_to_out(record))
    return {"success": True, "data": saved, "count": len(saved), "message": f"已导入 {len(saved)} 道候选题"}

@router.post("/status")
def update_exercise_status(req: ExerciseStatusRequest, book_name: str = "default"):
    record = _bank(book_name).get(req.id)
    if not record:
        return {"success": False, "message": "未找到该习题"}
    record.status = req.status.strip() or "new"
    _bank(book_name).update(record)
    return {"success": True, "message": "状态已更新", "data": _record_to_out(record)}



@router.post("/practice")
def practice_exercise(req: ExercisePracticeRequest, book_name: str = "default"):
    bank = _bank(book_name)
    record = bank.record_practice(req.id, user_answer=req.user_answer, quality=req.quality, add_note=req.note)
    if not record:
        return {"success": False, "message": "未找到该习题"}

    _log_learning_event("exercise_practiced", book_name=book_name, record=record, payload={"quality": req.quality, "status": record.status, "add_to_mistake": req.add_to_mistake})
    mistake_id = ""
    if req.add_to_mistake:
        mb = get_mistake_book(book_name, str(PROGRESS_PATH))
        mistake_id = mb.add(_mistake_from_exercise(record, user_answer=req.user_answer))
        _log_learning_event("exercise_to_mistake", book_name=book_name, record=record, payload={"mistake_id": mistake_id, "trigger": "practice"})
    return {"success": True, "message": "练习结果已记录", "data": _record_to_out(record), "mistake_id": mistake_id}


@router.post("/to-mistake")
def exercise_to_mistake(req: ExerciseToMistakeRequest, book_name: str = "default"):
    record = _bank(book_name).get(req.id)
    if not record:
        return {"success": False, "message": "未找到该习题"}
    mb = get_mistake_book(book_name, str(PROGRESS_PATH))
    mistake_id = mb.add(_mistake_from_exercise(record, user_answer=req.user_answer, mistake_type=req.mistake_type))
    _log_learning_event("exercise_to_mistake", book_name=book_name, record=record, payload={"mistake_id": mistake_id, "trigger": "manual"})
    record.status = "needs_review"
    _bank(book_name).update(record)
    return {"success": True, "message": "已转入错题本", "id": mistake_id, "data": _record_to_out(record)}


@router.post("/from-mistake")
def add_from_mistake(req: ExerciseFromMistakeRequest, book_name: str = "default"):
    mb = get_mistake_book(book_name, str(PROGRESS_PATH))
    mistake = mb.get(req.mistake_id)
    if not mistake:
        return {"success": False, "message": "未找到该错题"}

    bank = _bank(book_name)
    existing = bank.find_by_origin("mistake", mistake.id)
    if existing:
        return {"success": True, "message": "该错题已在习题库中", "data": _record_to_out(existing), "id": existing.id}

    record = ExerciseRecord(
        question_text=mistake.question_text,
        answer=mistake.correct_answer,
        explanation=mistake.explanation,
        source=mistake.source,
        subject=mistake.subject or book_name,
        chapter=mistake.chapter,
        tags=mistake.tags,
        question_type="错题转入",
        difficulty=mistake.difficulty,
        image_path=mistake.image_path,
        ocr_text=mistake.ocr_text,
        linked_concepts=mistake.linked_concepts,
        origin_type="mistake",
        origin_id=mistake.id,
        status="needs_review",
        notes="由错题本转入",
    )
    rid = bank.add(record)
    _log_learning_event("exercise_added", book_name=book_name, record=record, payload={"origin_type": record.origin_type, "origin_id": record.origin_id})
    return {"success": True, "message": "已从错题转入习题库", "id": rid, "data": _record_to_out(record)}

@router.get("/{exercise_id}")
def get_exercise_detail(exercise_id: str, book_name: str = "default"):
    record = _bank(book_name).get(exercise_id)
    if not record:
        return {"success": False, "message": "未找到该习题"}
    return {"success": True, "data": _record_to_out(record)}


@router.delete("/{exercise_id}")
def delete_exercise(exercise_id: str, book_name: str = "default"):
    _bank(book_name).delete(exercise_id)
    return {"success": True, "message": f"已删除 {exercise_id}"}
