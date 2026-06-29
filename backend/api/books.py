"""Books API: textbook management and asynchronous MinerU import jobs."""
from __future__ import annotations

import json
import re
import shutil
import threading
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile

from backend.schemas import PreReadStatusOut
from config import BOOKS_PATH, PROGRESS_PATH
from ingestion.background_reader import BackgroundReader
from ingestion.mineru_importer import import_textbook, import_textbook_local
from ingestion.pdf_parser import PDFParser

router = APIRouter(prefix="/books", tags=["books"])

_book_state: dict = {
    "current_book": None,
    "chapters": [],
    "book_pdf_path": None,
    "bg_reader": None,
}

JOB_DIR = Path(PROGRESS_PATH) / "import_jobs"
_jobs_lock = threading.Lock()


def _get_books() -> list[Path]:
    BOOKS_PATH.mkdir(parents=True, exist_ok=True)
    return list(BOOKS_PATH.glob("*.pdf"))


def _load_chapters(name: str) -> list[dict]:
    path = Path(PROGRESS_PATH) / name / "_chapters.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return []


def _format_chapter(ch: dict) -> dict:
    return {
        "title": ch.get("title", ""),
        "page": ch.get("page_number", ch.get("page", 1)),
        "end_page": ch.get("end_page"),
        "subsections": [
            {
                "title": sub.get("title", ""),
                "page": sub.get("page", sub.get("page_number")),
                "end_page": sub.get("end_page"),
            }
            for sub in ch.get("subsections", [])
        ],
    }


def _save_chapters(name: str, chapters: list[dict]) -> None:
    path = Path(PROGRESS_PATH) / name / "_chapters.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(chapters, fh, ensure_ascii=False, indent=2)


def _safe_pdf_name(filename: str) -> str:
    raw = Path(filename or "textbook.pdf").name
    stem = re.sub(r"[^\w\-.\u4e00-\u9fff]+", "_", Path(raw).stem).strip("._") or "textbook"
    return f"{stem[:90]}.pdf"


def _save_upload(file: UploadFile) -> Path:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise ValueError("请上传 PDF 教材")
    BOOKS_PATH.mkdir(parents=True, exist_ok=True)
    dest = BOOKS_PATH / _safe_pdf_name(file.filename)
    base = dest.with_suffix("")
    suffix = dest.suffix
    counter = 1
    while dest.exists():
        dest = Path(f"{base}_{counter}{suffix}")
        counter += 1
    with open(dest, "wb") as fh:
        shutil.copyfileobj(file.file, fh)
    return dest


def _job_path(job_id: str) -> Path:
    return JOB_DIR / f"{job_id}.json"


def _write_job(job: dict) -> None:
    JOB_DIR.mkdir(parents=True, exist_ok=True)
    job["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with _jobs_lock:
        _job_path(job["id"]).write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_job(job_id: str) -> dict | None:
    path = _job_path(job_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _update_job(job_id: str, **updates) -> dict:
    job = _read_job(job_id) or {"id": job_id}
    job.update(updates)
    _write_job(job)
    return job


def _set_current_book(book_name: str, chapters: list[dict], pdf_path: Path) -> None:
    _book_state["current_book"] = book_name
    _book_state["chapters"] = chapters
    _book_state["book_pdf_path"] = str(pdf_path)


def _run_import_job(job_id: str, pdf_path: Path, toc_pages: str, pre_read: bool, require_mineru: bool) -> None:
    book_name = pdf_path.stem

    def progress(stage: str, message: str, percent: int | None = None) -> None:
        payload = {"stage": stage, "message": message}
        if percent is not None:
            payload["progress"] = max(0, min(100, int(percent)))
        _update_job(job_id, **payload)

    try:
        progress("started", "准备导入教材", 3)
        result = import_textbook(pdf_path, book_name, toc_pages=toc_pages, require_mineru=require_mineru, on_progress=progress)
        _save_chapters(book_name, result.chapters)
        _set_current_book(book_name, result.chapters, pdf_path)
        if pre_read and result.chapters and not result.used_mineru:
            _start_pre_read(book_name, result.chapters, pdf_path)
        _update_job(
            job_id,
            status="completed",
            stage="completed",
            progress=100,
            message=result.message or "教材导入完成",
            result={
                "name": book_name,
                "chapter_count": len(result.chapters),
                "used_mineru": result.used_mineru,
                "indexed_chunks": result.indexed_chunks,
                "output_dir": result.output_dir,
            },
        )
    except Exception as exc:
        _update_job(job_id, status="failed", stage="failed", progress=100, message=f"教材导入失败：{exc}")


@router.get("/list")
def list_books():
    books = _get_books()
    return {
        "success": True,
        "data": [{"name": p.stem, "path": str(p), "size": p.stat().st_size} for p in books],
    }


@router.get("/current")
def get_current_book():
    name = _book_state.get("current_book")
    if not name:
        return {"success": False, "message": "未选择教材"}
    chapters = _book_state.get("chapters", [])
    return {"success": True, "data": {"name": name, "chapter_count": len(chapters), "chapters": [_format_chapter(c) for c in chapters]}}


@router.get("/switch/{book_name}")
def switch_book(book_name: str):
    pdfs = {p.stem: p for p in _get_books()}
    if book_name not in pdfs:
        return {"success": False, "message": f"教材不存在: {book_name}"}

    pdf_path = pdfs[book_name]
    chapters = _load_chapters(book_name)
    if not chapters and pdf_path.exists():
        parser = PDFParser(pdf_path)
        try:
            chapters = parser.extract_chapters()
        finally:
            parser.close()
        _save_chapters(book_name, chapters)

    _set_current_book(book_name, chapters, pdf_path)
    return {"success": True, "data": {"name": book_name, "chapter_count": len(chapters), "chapters": [_format_chapter(c) for c in chapters]}}


@router.post("/import-job")
def create_import_job(
    file: UploadFile = File(...),
    toc_pages: str = Form(""),
    pre_read: bool = Form(False),
    require_mineru: bool = Form(True),
):
    try:
        pdf_path = _save_upload(file)
    except Exception as exc:
        return {"success": False, "message": str(exc)}

    job_id = uuid.uuid4().hex
    job = {
        "id": job_id,
        "status": "running",
        "stage": "queued",
        "progress": 0,
        "message": "已加入导入队列",
        "book_name": pdf_path.stem,
        "file_path": str(pdf_path),
        "result": None,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _write_job(job)
    thread = threading.Thread(target=_run_import_job, args=(job_id, pdf_path, toc_pages, pre_read, require_mineru), daemon=True)
    thread.start()
    return {"success": True, "message": "教材导入任务已启动", "job_id": job_id, "data": job}


@router.post("/import")
def import_book(
    file: UploadFile = File(...),
    toc_pages: str = Form(""),
    pre_read: bool = Form(False),
):
    return create_import_job(file=file, toc_pages=toc_pages, pre_read=pre_read, require_mineru=True)


@router.get("/import-jobs/{job_id}")
def get_import_job(job_id: str):
    job = _read_job(job_id)
    if not job:
        return {"success": False, "message": "未找到导入任务"}
    return {"success": True, "data": job}


@router.post("/import-local")
def import_book_local(
    file: UploadFile = File(...),
    toc_pages: str = Form(""),
):
    try:
        pdf_path = _save_upload(file)
        result = import_textbook_local(pdf_path, pdf_path.stem, toc_pages=toc_pages)
        _save_chapters(pdf_path.stem, result.chapters)
        _set_current_book(pdf_path.stem, result.chapters, pdf_path)
        return {
            "success": True,
            "message": result.message,
            "data": {"name": pdf_path.stem, "chapter_count": len(result.chapters), "used_mineru": False},
        }
    except Exception as exc:
        return {"success": False, "message": f"本地导入失败：{exc}"}


def _start_pre_read(book_name: str, chapters: list[dict], pdf_path: Path) -> None:
    bg = _book_state.get("bg_reader")
    if bg and getattr(bg, "_running", False):
        return
    reader = BackgroundReader(book_name, chapters, pdf_path)
    reader.start()
    _book_state["bg_reader"] = reader


@router.post("/preread/start")
def start_pre_read():
    name = _book_state.get("current_book")
    chapters = _book_state.get("chapters", [])
    pdf_path = _book_state.get("book_pdf_path")
    if not name or not chapters or not pdf_path:
        return {"success": False, "message": "请先选择教材"}
    if len(chapters) < 2:
        return {"success": False, "message": "章节数量不足，无需预读"}
    _start_pre_read(name, chapters, Path(pdf_path))
    return {"success": True, "message": f"预读已启动 ({len(chapters)}章)"}


@router.get("/preread/status")
def pre_read_status():
    bg = _book_state.get("bg_reader")
    if bg:
        status = bg.status
        if status.get("running"):
            return PreReadStatusOut(running=True, done=status.get("done", 0), total=status.get("total", 0), status_text=f"预读 {status['done']}/{status['total']}")
        if status.get("done", 0) > 0:
            return PreReadStatusOut(running=False, done=status.get("done", 0), total=status.get("total", 0), status_text=f"完成 {status['done']}/{status['total']}")
    return PreReadStatusOut(status_text="")
