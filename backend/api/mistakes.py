"""Mistakes API: CRUD, review, Kimi OCR, and DeepSeek explanations."""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from fastapi.responses import FileResponse

from backend.schemas import (
    MistakeAddRequest,
    MistakeExplainRequest,
    MistakeListRequest,
    MistakeRecordOut,
    MistakeReviewRequest,
    MistakeStatsOut,
    WeakPointOut,
)
from config import IMAGES_PATH, PROGRESS_PATH
from memory.mistake_book import MistakeRecord, get_mistake_book
from memory.learning_events import LearningEvent, concept_names, get_learning_event_store
from utils.latex_sanitizer import sanitize_latex
from utils.subject_catalog import normalize_subject_value
from utils.thinking_filter import strip_thinking

router = APIRouter(prefix="/mistakes", tags=["mistakes"])

ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024
OCR_MAX_SIDE = int(os.getenv("MISTAKE_OCR_MAX_SIDE", "1600"))
OCR_JPEG_QUALITY = int(os.getenv("MISTAKE_OCR_JPEG_QUALITY", "86"))
KIMI_VISION_MODEL = os.getenv("KIMI_VISION_MODEL", "kimi-k2.5")
PENDING_IMAGE_MAX_AGE_SECONDS = 24 * 60 * 60


def _log_learning_event(event_type: str, *, book_name: str = "default", record: MistakeRecord | None = None, payload: dict | None = None) -> None:
    try:
        get_learning_event_store().append(LearningEvent(
            event_type=event_type,
            book_name=book_name,
            subject=record.subject if record else "",
            source_type="mistake",
            source_id=record.id if record else "",
            concept_names=concept_names(record.linked_concepts if record else []),
            payload=payload or {},
        ))
    except Exception as exc:
        print(f"[LearningEvent] mistake event failed: {exc}", flush=True)


def _mb(book_name: str = "default"):
    return get_mistake_book(book_name, str(PROGRESS_PATH))


def _record_to_out(record: MistakeRecord) -> MistakeRecordOut:
    return MistakeRecordOut(
        id=record.id,
        book_id=record.book_id,
        question_text=record.question_text,
        user_answer=record.user_answer,
        correct_answer=record.correct_answer,
        source=record.source,
        subject=record.subject,
        chapter=record.chapter,
        tags=record.tags,
        mistake_type=record.mistake_type,
        difficulty=record.difficulty,
        created_at=record.created_at,
        image_path=record.image_path,
        ocr_text=record.ocr_text,
        explanation=record.explanation,
        linked_concepts=record.linked_concepts,
        review_history=record.review_history,
        next_review=record.sm2.get("next_review") if record.sm2 else None,
        interval=record.sm2.get("interval") if record.sm2 else None,
    )


def _tags_from_text(tags: str) -> list[str]:
    return [item.strip() for item in tags.split(",") if item.strip()]


def _record_from_request(req: MistakeAddRequest, book_name: str = "default") -> MistakeRecord:
    return MistakeRecord(
        question_text=req.question_text.strip(),
        user_answer=req.user_answer.strip(),
        correct_answer=req.correct_answer.strip(),
        source=req.source.strip(),
        subject=normalize_subject_value(req.subject, fallback=book_name),
        chapter=req.chapter.strip() or None,
        tags=_tags_from_text(req.tags),
        mistake_type=req.mistake_type,
        difficulty=max(1, min(5, int(req.difficulty or 3))),
        image_path=req.image_path,
        ocr_text=req.ocr_text.strip(),
        explanation=sanitize_latex(strip_thinking(req.explanation.strip())) if req.explanation.strip() else "",
    )


def _parse_keyword_json(text: str) -> list[str]:
    cleaned = strip_thinking(text or "").strip()
    match = re.search(r"\[[\s\S]*\]", cleaned)
    if match:
        cleaned = match.group(0)
    try:
        data = json.loads(cleaned)
    except Exception:
        data = [line.strip(" -??,\t") for line in cleaned.splitlines() if line.strip()]

    keywords: list[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                name = item.strip()
            elif isinstance(item, dict):
                name = str(item.get("name") or item.get("concept") or "").strip()
            else:
                name = ""
            if name and name not in keywords:
                keywords.append(name)
            if len(keywords) >= 3:
                break
    return keywords


def _extract_mistake_keywords_with_llm(record: MistakeRecord, explanation: str = "") -> list[str]:
    try:
        from config import get_llm

        prompt = f"""Extract 1 to 3 key academic concepts or method names from this mistaken problem.

Rules:
1. Return only concepts that are central to the problem, not generic words such as method, step, condition, or problem.
2. Prefer standard textbook / knowledge-graph terminology.
3. Output only a JSON array of strings, for example ["limit", "L'Hopital rule"]. Do not explain.

Question:
{record.question_text[:1600]}

Correct answer:
{record.correct_answer[:600] or "not provided"}

Explanation:
{explanation[:1600] or record.explanation[:1600] or "not generated"}
"""
        result = get_llm().invoke(prompt).content
        return _parse_keyword_json(result)
    except Exception as e:
        print(f"[MistakeConcepts] LLM keyword extraction failed: {e}", flush=True)
        return []


def _dedupe_concepts(concepts: list[dict], limit: int = 3) -> list[dict]:
    result: list[dict] = []
    seen: set[str] = set()
    for item in concepts:
        name = str(item.get("name", "")).strip()
        cid = str(item.get("concept_id", "")).strip()
        key = cid or name
        if not name or key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def _link_mistake_concepts(record: MistakeRecord, explanation: str = "", book_name: str = "default") -> list[dict]:
    try:
        from knowledge.concept_linker import ConceptLinker

        linker = ConceptLinker(book_name)
        if not getattr(linker.kg, "_is_local", False):
            return []

        concepts: list[dict] = []
        for keyword in _extract_mistake_keywords_with_llm(record, explanation):
            linked = linker.link(matched_concepts=[keyword], question=keyword, intent="mistake", limit=1)
            if not linked:
                linked = linker.link(question=keyword, intent="mistake", limit=1)
            for item in linked:
                item = dict(item)
                item["confidence"] = 1.0
                item["source"] = "mistake_llm"
                item["evidence"] = keyword
                concepts.append(item)

        if not concepts:
            question = "\n".join(part for part in [record.question_text, record.correct_answer] if part)
            concepts = linker.link(
                question=question,
                answer=explanation or record.explanation,
                tags=record.tags,
                intent="mistake",
                limit=3,
            )
            for item in concepts:
                item["confidence"] = max(float(item.get("confidence", 0) or 0), 0.999)
                item["source"] = "mistake_linker"

        return _dedupe_concepts(concepts, limit=3)
    except Exception as e:
        print(f"[MistakeConcepts] KG linking failed: {e}", flush=True)
        return []


def _persist_mistake_concepts(record: MistakeRecord, explanation: str = "", book_name: str = "default") -> list[dict]:
    concepts = _link_mistake_concepts(record, explanation=explanation, book_name=book_name)
    if not concepts:
        return []
    record.linked_concepts = concepts
    try:
        from knowledge.concept_memory import ConceptMemory

        ConceptMemory(book_name).log_weakness(concepts, record.question_text, "mistake", source="mistake", subject=record.subject)
    except Exception as e:
        print(f"[ConceptMemory] mistake record failed: {e}", flush=True)
    return concepts


def _image_root() -> Path:
    return Path(IMAGES_PATH) / "mistakes"


def _pending_image_root() -> Path:
    return _image_root() / "pending"


def _delete_mistake_image(path: str | Path | None) -> None:
    if not path:
        return
    candidate = Path(path).resolve()
    root = _image_root().resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return
    candidate.unlink(missing_ok=True)


def _cleanup_stale_pending_images() -> None:
    pending = _pending_image_root()
    if not pending.exists():
        return
    cutoff = time.time() - PENDING_IMAGE_MAX_AGE_SECONDS
    for path in pending.iterdir():
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except OSError:
            continue


def _commit_pending_mistake_image(path: str | None) -> tuple[str | None, bool]:
    if not path:
        return None, False
    source = Path(path).resolve()
    root = _image_root().resolve()
    pending = _pending_image_root().resolve()
    try:
        source.relative_to(root)
    except ValueError:
        raise ValueError("图片路径不在错题图片目录内")
    if not source.exists() or not source.is_file():
        raise ValueError("待保存图片不存在")
    try:
        source.relative_to(pending)
    except ValueError:
        return str(source), False

    root.mkdir(parents=True, exist_ok=True)
    destination = root / source.name
    if destination.exists():
        destination = root / f"{uuid.uuid4().hex}_{source.name}"
    shutil.move(str(source), str(destination))
    return str(destination), True


def _save_uploaded_image(file: UploadFile) -> Path:
    filename = file.filename or "mistake.png"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTS:
        raise ValueError("请上传 png/jpg/jpeg/webp/bmp 格式的图片")

    _cleanup_stale_pending_images()
    out_dir = _pending_image_root()
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / f"{uuid.uuid4().hex}_raw{suffix}"

    size = 0
    with open(raw_path, "wb") as fh:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_IMAGE_BYTES:
                fh.close()
                raw_path.unlink(missing_ok=True)
                raise ValueError("图片不能超过 20MB")
            fh.write(chunk)
    return _optimize_for_ocr(raw_path)


def _optimize_for_ocr(raw_path: Path) -> Path:
    optimized_path = raw_path.with_name(raw_path.stem.replace("_raw", "") + "_ocr.jpg")
    try:
        from PIL import Image, ImageOps

        with Image.open(raw_path) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            width, height = img.size
            scale = min(1.0, OCR_MAX_SIDE / max(width, height))
            if scale < 1.0:
                next_size = (max(1, int(width * scale)), max(1, int(height * scale)))
                img = img.resize(next_size, Image.Resampling.LANCZOS)
            if img.mode == "L":
                img = img.convert("RGB")
            img.save(optimized_path, format="JPEG", quality=OCR_JPEG_QUALITY, optimize=True)
        raw_path.unlink(missing_ok=True)
        return optimized_path
    except Exception:
        optimized_path.unlink(missing_ok=True)
        return raw_path


def _image_data_url(image_path: Path) -> str:
    mime = "image/jpeg" if image_path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _ocr_image_with_kimi(image_path: Path) -> str:
    moonshot_api_key = os.getenv("MOONSHOT_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    moonshot_api_base = os.getenv("MOONSHOT_API_BASE", "https://api.moonshot.cn/v1")
    kimi_vision_model = os.getenv("KIMI_VISION_MODEL", KIMI_VISION_MODEL)
    if not moonshot_api_key:
        raise RuntimeError("未配置 MOONSHOT_API_KEY，无法调用 Kimi Vision OCR")

    import httpx
    from openai import OpenAI

    client = OpenAI(
        api_key=moonshot_api_key,
        base_url=moonshot_api_base,
        http_client=httpx.Client(trust_env=False, timeout=120),
    )
    prompt = """请只做 OCR/题目转写，不要解题。
任务：完整转写图片中的考研数学或专业课错题，包含题干、条件、选项、图表文字、公式和能看清的手写答案。
要求：
1. 数学公式使用 LaTeX，行内公式用 $...$，独立公式用 $$...$$。
2. 保留题目结构，如小问、选项、矩阵、分段函数、约束条件。
3. 无法确定的字符用 [不确定: ...] 标注，不要臆造。
4. 只输出转写文本，不要解释、不要解题、不要寒暄。"""
    resp = client.chat.completions.create(
        model=kimi_vision_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": _image_data_url(image_path)}},
                ],
            }
        ],
        timeout=120,
    )
    return (resp.choices[0].message.content or "").strip()

def _build_image_solution_prompt(ocr_text: str, user_answer: str = "", subject: str = "", tags: str = "") -> str:
    return f"""你是考研数学与专业课错题讲解助手。请根据 OCR 转写出的题目内容进行解答。OCR 可能有误，若发现明显识别错误，请先给出你修正后的题意，再开始解题。

## 题目 OCR
{ocr_text or '（OCR 未识别到文字，请说明无法可靠看清题目，并提示用户手动补充题干。）'}

## 用户答案
{user_answer or '（未提供）'}

## 学科/标签
{subject or '（未填写）'} {tags or ''}

## 输出要求
1. 先复原题意，必要时说明 OCR 不确定处。
2. 给出完整解题步骤，公式使用 LaTeX。
3. 如果用户答案不为空，指出具体错误位置。
4. 最后总结本题考点和易错点。
直接输出讲解内容，不要寒暄，不要输出 thinking。"""

def _solve_ocr_text(ocr_text: str, user_answer: str = "", subject: str = "", tags: str = "") -> str:
    from config import get_llm

    prompt = _build_image_solution_prompt(ocr_text, user_answer=user_answer, subject=subject, tags=tags)
    result = get_llm().invoke(prompt).content
    return sanitize_latex(strip_thinking(result))


@router.post("/add")
def add_mistake(req: MistakeAddRequest, book_name: str = "default"):
    committed_image: str | None = None
    image_was_moved = False
    try:
        committed_image, image_was_moved = _commit_pending_mistake_image(req.image_path)
        record = _record_from_request(req, book_name=book_name)
        record.image_path = committed_image
        _persist_mistake_concepts(record, explanation=record.explanation, book_name=book_name)
        mid = _mb(book_name).add(record)
        _log_learning_event("mistake_added", book_name=book_name, record=record, payload={"difficulty": record.difficulty, "mistake_type": record.mistake_type, "tags": record.tags})
        return {"success": True, "id": mid, "data": _record_to_out(record), "message": f"已保存（{mid}）"}
    except Exception as e:
        if image_was_moved:
            _delete_mistake_image(committed_image)
        return {
            "success": False,
            "message": f"保存失败：{e}。如果提示 disk I/O error，请检查 data/progress 的 SQLite 文件权限或残留 journal。",
        }

@router.post("/list")
def list_mistakes(req: MistakeListRequest, book_name: str = "default"):
    records = _mb(book_name).list_all(
        subject=req.subject or None,
        chapter=req.chapter or None,
        tag=req.tag or None,
        limit=req.limit,
    )
    if req.search_kw.strip():
        kw = req.search_kw.strip().lower()
        records = [
            r
            for r in records
            if kw in r.question_text.lower()
            or kw in r.ocr_text.lower()
            or kw in r.explanation.lower()
            or any(kw in t.lower() for t in r.tags)
        ]
    return {"success": True, "data": [_record_to_out(r) for r in records]}


@router.get("/due")
def get_due_mistakes(subject: str = "", book_name: str = "default"):
    records = _mb(book_name).get_due(subject=subject or None)
    return {"success": True, "data": [_record_to_out(r) for r in records]}


@router.post("/recognize-image")
def recognize_mistake_image(file: UploadFile = File(...)):
    image_path: Path | None = None
    try:
        image_path = _save_uploaded_image(file)
        ocr_text = _ocr_image_with_kimi(image_path)
        if not ocr_text:
            _delete_mistake_image(image_path)
            return {
                "success": False,
                "message": "Kimi Vision 未返回有效 OCR 文本，请手动输入题干后保存。",
                "ocr_text": "",
            }
        return {
            "success": True,
            "message": "Kimi Vision 识别完成，请先校对题干再保存或解答。",
            "image_path": str(image_path),
            "ocr_text": ocr_text,
            "ocr_provider": "kimi-vision",
            "optimized": image_path.name.endswith("_ocr.jpg"),
        }
    except Exception as e:
        _delete_mistake_image(image_path)
        return {"success": False, "message": f"讲解失败: {e}"}

@router.post("/solve-image")
def solve_mistake_image(
    file: UploadFile = File(...),
    user_answer: str = Form(""),
    subject: str = Form(""),
    tags: str = Form(""),
):
    image_path: Path | None = None
    try:
        image_path = _save_uploaded_image(file)
        ocr_text = _ocr_image_with_kimi(image_path)
        if not ocr_text:
            _delete_mistake_image(image_path)
            return {
                "success": False,
                "message": "Kimi Vision 未返回有效 OCR 文本，请手动补充题干后再解答。",
                "ocr_text": "",
            }
        explanation = _solve_ocr_text(ocr_text, user_answer=user_answer, subject=subject, tags=tags)
        return {
            "success": True,
            "message": "已由 Kimi Vision 识题，并交给 DeepSeek 生成讲解。请校对 OCR 文本。",
            "image_path": str(image_path),
            "ocr_text": ocr_text,
            "ocr_provider": "kimi-vision",
            "optimized": image_path.name.endswith("_ocr.jpg"),
            "explanation": explanation,
        }
    except Exception as e:
        _delete_mistake_image(image_path)
        return {"success": False, "message": f"讲解失败: {e}"}

@router.post("/solve-text")
def solve_mistake_text(req: MistakeAddRequest):
    try:
        explanation = _solve_ocr_text(
            req.question_text.strip(),
            user_answer=req.user_answer.strip(),
            subject=req.subject.strip(),
            tags=req.tags.strip(),
        )
        return {"success": True, "explanation": explanation}
    except Exception as e:
        return {"success": False, "message": f"讲解失败: {e}"}

@router.get("/stats")
def get_stats(subject: str = "", book_name: str = "default") -> MistakeStatsOut:
    stats = _mb(book_name).get_stats(subject=subject or None)
    return MistakeStatsOut(
        total=stats["total"],
        due_today=stats["due_today"],
        by_type=stats.get("by_type", {}),
        by_tag=stats.get("by_tag", {}),
        by_difficulty=stats.get("by_difficulty", {}),
    )


@router.get("/weak-points")
def get_weak_points(subject: str = "", book_name: str = "default", top_n: int = 8):
    weak = _mb(book_name).get_weak_points(subject=subject or None, top_n=top_n)
    return {"success": True, "data": [WeakPointOut(name=w["name"], type=w["type"], count=w["count"]) for w in weak]}



@router.get("/{mistake_id}/image")
def get_mistake_image(mistake_id: str, book_name: str = "default"):
    record = _mb(book_name).get(mistake_id)
    if not record or not record.image_path:
        raise HTTPException(status_code=404, detail="image not found")
    image_path = Path(record.image_path).resolve()
    image_root = (Path(IMAGES_PATH) / "mistakes").resolve()
    try:
        image_path.relative_to(image_root)
    except ValueError:
        raise HTTPException(status_code=403, detail="image path forbidden")
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="image file not found")
    return FileResponse(str(image_path))

@router.get("/{mistake_id}")
def get_mistake_detail(mistake_id: str, book_name: str = "default"):
    record = _mb(book_name).get(mistake_id)
    if not record:
        return {"success": False, "message": "错题不存在"}
    return {"success": True, "data": _record_to_out(record)}

@router.delete("/{mistake_id}")
def delete_mistake(mistake_id: str, book_name: str = "default"):
    mistake_book = _mb(book_name)
    record = mistake_book.get(mistake_id)
    mistake_book.delete(mistake_id)
    if record:
        _delete_mistake_image(record.image_path)
    return {"success": True, "message": f"已删除 {mistake_id}"}

@router.post("/review")
def review_mistake(req: MistakeReviewRequest, book_name: str = "default"):
    try:
        updated = _mb(book_name).review(req.id, req.quality)
        _log_learning_event("mistake_reviewed", book_name=book_name, record=updated, payload={"quality": req.quality, "next_review": updated.sm2.get("next_review") if updated.sm2 else None})
        next_review = updated.sm2.get("next_review") if updated.sm2 else None
        interval = updated.sm2.get("interval") if updated.sm2 else None
        return {
            "success": True,
            "message": f"已记录复习，{interval or 1} 天后再看",
            "data": _record_to_out(updated),
            "next_review": next_review,
            "interval": interval,
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

def _record_mistake_concepts(record: MistakeRecord, explanation: str, rag_context: str, book_name: str) -> list[dict]:
    return _persist_mistake_concepts(record, explanation=explanation or rag_context, book_name=book_name)


@router.post("/explain")
def explain_mistake(req: MistakeExplainRequest, book_name: str = "default"):
    from config import get_llm
    from graph.safe_retrieval import get_safe_vector_store

    mb = _mb(book_name)
    llm = get_llm()
    rag_context = {"text": ""}
    rag_book = (req.book_name or book_name or "").strip()

    def rag_provider(record: MistakeRecord):
        if not rag_book:
            return ""
        try:
            vs, vector_error = get_safe_vector_store()
            if vector_error:
                return ""
            if vs and record.tags:
                ch_docs = vs.search_all(record.tags[0], k=3, book_name=rag_book)
                texts = []
                for chapter, docs in ch_docs.items():
                    texts.append("章节：" + chapter)
                    for doc in docs:
                        texts.append(doc.page_content[:400])
                rag_context["text"] = "\n".join(texts)
                return rag_context["text"]
        except Exception:
            pass
        return ""

    try:
        result = mb.explain(req.id, lambda prompt: strip_thinking(llm.invoke(prompt).content), context_provider=rag_provider)
        sanitized = sanitize_latex(result)
        record = mb.get(req.id)
        if record:
            record.explanation = sanitized
            _record_mistake_concepts(record, sanitized, rag_context["text"], req.book_name or book_name)
            mb.update(record)
            _log_learning_event("mistake_explained", book_name=req.book_name or book_name, record=record, payload={"has_rag_context": bool(rag_context["text"])})
        return {"success": True, "explanation": sanitized, "data": _record_to_out(record) if record else None}
    except Exception as e:
        return {"success": False, "message": f"讲解失败: {e}"}
