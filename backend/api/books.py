"""Books API: textbook management and asynchronous MinerU import jobs."""
from __future__ import annotations

import json
import re
import shutil
import threading
import time
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel

from backend.job_manager import JobCancelled, get_job_manager
from backend.schemas import PreReadStatusOut
from config import BOOKS_PATH, DATA_DIR, MINERU_OUTPUT_PATH, PROGRESS_PATH
from ingestion.background_reader import BackgroundReader
from ingestion.mineru_importer import import_textbook, import_textbook_from_mineru_output, import_textbook_local
from ingestion.pdf_parser import PDFParser
from utils.json_io import atomic_write_json
from utils.path_safety import safe_book_name, safe_child_path
from utils.subject_catalog import normalize_subject_value

router = APIRouter(prefix="/books", tags=["books"])


class BookUpdateRequest(BaseModel):
    subject: str | None = None


_book_state: dict = {
    "current_book": None,
    "chapters": [],
    "book_pdf_path": None,
    "bg_reader": None,
}

IMPORT_JOB_TYPE = "textbook_import"
OUTPUT_UPLOAD_DIR = DATA_DIR / "uploads" / "mineru_outputs"
_job_manager = get_job_manager()
_job_manager.import_legacy_json_jobs(
    IMPORT_JOB_TYPE,
    Path(PROGRESS_PATH) / "import_jobs",
    input_keys=("book_name", "file_path", "toc_pages", "pre_read", "require_mineru", "subject"),
)


def _get_books() -> list[Path]:
    BOOKS_PATH.mkdir(parents=True, exist_ok=True)
    return list(BOOKS_PATH.glob("*.pdf"))


def _known_book_names(include_archived: bool = False) -> list[str]:
    names = {p.stem for p in _get_books()}
    progress_root = Path(PROGRESS_PATH)
    if progress_root.exists():
        for child in progress_root.iterdir():
            if child.is_dir() and (child / "_chapters.json").exists():
                names.add(child.name)
    if not include_archived:
        names = {name for name in names if not _read_book_meta(name).get("archived")}
    return sorted(names)


def _book_pdf_path(name: str) -> Path | None:
    candidate = BOOKS_PATH / f"{Path(name).name}.pdf"
    return candidate if candidate.exists() else None


def _load_chapters(name: str) -> list[dict]:
    path = safe_child_path(PROGRESS_PATH, safe_book_name(name), "_chapters.json")
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
    path = safe_child_path(PROGRESS_PATH, safe_book_name(name), "_chapters.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, chapters)


def _book_meta_path(name: str) -> Path:
    return safe_child_path(PROGRESS_PATH, safe_book_name(name), "metadata.json")


def _read_book_meta(name: str) -> dict:
    path = _book_meta_path(name)
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _write_book_meta(name: str, **updates) -> dict:
    path = _book_meta_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = _read_book_meta(name)
    meta.update({k: v for k, v in updates.items() if v is not None})
    atomic_write_json(path, meta)
    return meta


def _book_subject(name: str) -> str:
    return str(_read_book_meta(name).get("subject", "")).strip()


def _safe_pdf_name(filename: str) -> str:
    raw = Path(filename or "textbook.pdf").name
    stem = re.sub(r"[^\w\-.\u4e00-\u9fff]+", "_", Path(raw).stem).strip("._") or "textbook"
    return f"{stem[:90]}.pdf"


def _save_upload(file: UploadFile) -> Path:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise ValueError("\u8bf7\u4e0a\u4f20 PDF \u6559\u6750")
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


def _read_job(job_id: str) -> dict | None:
    return _job_manager.get_job(job_id, job_type=IMPORT_JOB_TYPE)


def _update_job(job_id: str, **updates) -> dict:
    return _job_manager.update_job(job_id, **updates)


def _set_current_book(book_name: str, chapters: list[dict], pdf_path: Path | None) -> None:
    _book_state["current_book"] = book_name
    _book_state["chapters"] = chapters
    _book_state["book_pdf_path"] = str(pdf_path) if pdf_path else ""


def _run_import_job(job_id: str, pdf_path: Path, toc_pages: str, pre_read: bool, require_mineru: bool, subject: str = "") -> None:
    book_name = pdf_path.stem

    def progress(stage: str, message: str, percent: int | None = None) -> None:
        _job_manager.raise_if_cancelled(job_id)
        payload = {"stage": stage, "message": message}
        if percent is not None:
            payload["progress"] = max(0, min(100, int(percent)))
        _update_job(job_id, **payload)

    try:
        progress("started", "\u51c6\u5907\u5bfc\u5165\u6559\u6750", 3)
        result = import_textbook(pdf_path, book_name, toc_pages=toc_pages, require_mineru=require_mineru, on_progress=progress)
        _save_chapters(book_name, result.chapters)
        _write_book_meta(book_name, subject=normalize_subject_value(subject))
        _set_current_book(book_name, result.chapters, pdf_path)
        if pre_read and result.chapters and not result.used_mineru:
            _start_pre_read(book_name, result.chapters, pdf_path)
        _update_job(
            job_id,
            status="completed",
            stage="completed",
            progress=100,
            message=result.message or "\u6559\u6750\u5bfc\u5165\u5b8c\u6210",
            result={
                "name": book_name,
                "chapter_count": len(result.chapters),
                "used_mineru": result.used_mineru,
                "indexed_chunks": result.indexed_chunks,
                "output_dir": result.output_dir,
                "subject": _book_subject(book_name),
            },
        )
    except JobCancelled as exc:
        _update_job(job_id, status="cancelled", stage="cancelled", progress=100, message=str(exc) or "\u6559\u6750\u5bfc\u5165\u5df2\u53d6\u6d88", error=str(exc))
    except Exception as exc:
        _update_job(job_id, status="failed", stage="failed", progress=100, message=f"\u6559\u6750\u5bfc\u5165\u5931\u8d25\uff1a{exc}", error=str(exc))


@router.get("/list")
def list_books():
    data = []
    for name in _known_book_names():
        pdf_path = _book_pdf_path(name)
        data.append({
            "name": name,
            "path": str(pdf_path) if pdf_path else "",
            "size": pdf_path.stat().st_size if pdf_path else 0,
            "subject": _book_subject(name),
            "has_pdf": bool(pdf_path),
            "chapter_count": len(_load_chapters(name)),
        })
    return {"success": True, "data": data}


@router.get("/current")
def get_current_book():
    name = _book_state.get("current_book")
    if not name:
        return {"success": False, "message": "\u672a\u9009\u62e9\u6559\u6750"}
    chapters = _book_state.get("chapters", [])
    return {"success": True, "data": {"name": name, "subject": _book_subject(name), "chapter_count": len(chapters), "chapters": [_format_chapter(c) for c in chapters]}}


@router.patch("/{book_name}")
def update_book(book_name: str, req: BookUpdateRequest):
    if book_name not in _known_book_names():
        return {"success": False, "message": f"Textbook not found: {book_name}"}

    updates = {}
    if req.subject is not None:
        updates["subject"] = normalize_subject_value(req.subject)

    meta = _write_book_meta(book_name, **updates) if updates else _read_book_meta(book_name)
    pdf_path = _book_pdf_path(book_name)
    chapters = _load_chapters(book_name)
    return {
        "success": True,
        "message": "\u6559\u6750\u4fe1\u606f\u5df2\u66f4\u65b0",
        "data": {
            "name": book_name,
            "path": str(pdf_path) if pdf_path else "",
            "size": pdf_path.stat().st_size if pdf_path else 0,
            "subject": str(meta.get("subject", "")).strip(),
            "has_pdf": bool(pdf_path),
            "chapter_count": len(chapters),
        },
    }


@router.delete("/{book_name}")
def archive_book(book_name: str):
    if book_name not in _known_book_names(include_archived=True):
        return {"success": False, "message": f"Textbook not found: {book_name}"}
    meta = _write_book_meta(book_name, archived=True)
    if _book_state.get("current_book") == book_name:
        _book_state["current_book"] = None
        _book_state["chapters"] = []
        _book_state["book_pdf_path"] = None
    return {
        "success": True,
        "message": "教材已从列表隐藏，本地文件、章节索引和学习记录未删除。",
        "data": {"name": book_name, "archived": bool(meta.get("archived"))},
    }


@router.get("/switch/{book_name}")
def switch_book(book_name: str):
    if book_name not in _known_book_names():
        return {"success": False, "message": f"Textbook not found: {book_name}"}

    pdf_path = _book_pdf_path(book_name)
    chapters = _load_chapters(book_name)
    if not chapters and pdf_path and pdf_path.exists():
        parser = PDFParser(pdf_path)
        try:
            chapters = parser.extract_chapters()
        finally:
            parser.close()
        _save_chapters(book_name, chapters)
    if not chapters:
        return {"success": False, "message": f"Textbook chapters not found: {book_name}"}

    _set_current_book(book_name, chapters, pdf_path)
    return {"success": True, "data": {"name": book_name, "subject": _book_subject(book_name), "chapter_count": len(chapters), "chapters": [_format_chapter(c) for c in chapters]}}



def _safe_output_book_name(value: str) -> str:
    raw = Path(value or "external_textbook").name
    stem = re.sub(r"[^\w\-.\u4e00-\u9fff]+", "_", Path(raw).stem).strip("._") or "external_textbook"
    return stem[:90]


def _save_output_upload(file: UploadFile, book_name: str) -> Path:
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise ValueError("Please upload a .zip file containing MinerU or Markdown output")
    OUTPUT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_book = _safe_output_book_name(book_name or file.filename)
    dest = OUTPUT_UPLOAD_DIR / f"{safe_book}_{int(time.time())}.zip"
    with open(dest, "wb") as fh:
        shutil.copyfileobj(file.file, fh)
    return dest


def _unique_output_dir(book_name: str) -> Path:
    base = MINERU_OUTPUT_PATH / _safe_output_book_name(book_name) / "hybrid_auto_external"
    dest = base
    counter = 1
    while dest.exists():
        dest = base.with_name(f"{base.name}_{counter}")
        counter += 1
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _extract_zip_safe(zip_path: Path, target_dir: Path) -> Path:
    root = target_dir.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if not name or name.startswith("/") or ".." in Path(name).parts:
                raise ValueError(f"Unsafe path in archive: {info.filename}")
            dest = (target_dir / name).resolve()
            if root != dest and root not in dest.parents:
                raise ValueError(f"Archive path escapes target directory: {info.filename}")
        zf.extractall(target_dir)
    return _detect_output_root(target_dir)


def _detect_output_root(target_dir: Path) -> Path:

    patterns = ["*content_list*.json", "*content-list*.json", "*middle*.json", "*.md"]
    for pattern in patterns:
        if list(target_dir.rglob(pattern)):
            break
    else:
        return target_dir

    direct_has = any(list(target_dir.glob(pattern)) for pattern in patterns)
    if direct_has:
        return target_dir
    children = [child for child in target_dir.iterdir() if child.is_dir()]
    if len(children) == 1:
        child = children[0]
        if any(list(child.rglob(pattern)) for pattern in patterns):
            return child
    return target_dir


def _copy_origin_pdf_if_present(output_dir: Path, book_name: str) -> Path | None:
    pdfs = sorted(output_dir.rglob("*.pdf"), key=lambda item: ("layout" in item.name.lower(), len(item.name)))
    if not pdfs:
        return None
    source = next((p for p in pdfs if "origin" in p.name.lower()), pdfs[0])
    BOOKS_PATH.mkdir(parents=True, exist_ok=True)
    dest = BOOKS_PATH / f"{_safe_output_book_name(book_name)}.pdf"
    if not dest.exists():
        shutil.copy2(source, dest)
    return dest


def _run_output_import_job(job_id: str, archive_path: Path, book_name: str, subject: str = "") -> None:
    def progress(stage: str, message: str, percent: int | None = None) -> None:
        _job_manager.raise_if_cancelled(job_id)
        payload = {"stage": stage, "message": message}
        if percent is not None:
            payload["progress"] = max(0, min(100, int(percent)))
        _update_job(job_id, **payload)

    try:
        progress("extract", "Extracting OCR output package", 10)
        output_dir = _extract_zip_safe(archive_path, _unique_output_dir(book_name))
        result = import_textbook_from_mineru_output(output_dir, book_name, on_progress=progress)
        _save_chapters(book_name, result.chapters)
        pdf_path = _copy_origin_pdf_if_present(output_dir, book_name)
        _write_book_meta(
            book_name,
            subject=normalize_subject_value(subject),
            import_source="external_mineru_output",
            mineru_output_dir=str(output_dir),
            source_archive=str(archive_path),
        )
        _set_current_book(book_name, result.chapters, pdf_path)
        _update_job(
            job_id,
            status="completed",
            stage="completed",
            progress=100,
            message=result.message or "OCR output import completed",
            result={
                "name": book_name,
                "chapter_count": len(result.chapters),
                "used_mineru": True,
                "indexed_chunks": result.indexed_chunks,
                "output_dir": result.output_dir,
                "subject": _book_subject(book_name),
                "has_pdf": bool(pdf_path),
            },
        )
    except JobCancelled as exc:
        _update_job(job_id, status="cancelled", stage="cancelled", progress=100, message=str(exc) or "OCR output import cancelled", error=str(exc))
    except Exception as exc:
        _update_job(job_id, status="failed", stage="failed", progress=100, message=f"OCR output import failed: {exc}", error=str(exc))

@router.post("/import-job")
def create_import_job(
    file: UploadFile = File(...),
    toc_pages: str = Form(""),
    pre_read: bool = Form(False),
    require_mineru: bool = Form(True),
    subject: str = Form(""),
):
    try:
        pdf_path = _save_upload(file)
    except Exception as exc:
        return {"success": False, "message": str(exc)}

    job = _job_manager.create_job(
        IMPORT_JOB_TYPE,
        {
            "book_name": pdf_path.stem,
            "file_path": str(pdf_path),
            "toc_pages": toc_pages,
            "pre_read": pre_read,
            "require_mineru": require_mineru,
            "subject": normalize_subject_value(subject),
        },
        status="running",
        stage="queued",
        progress=0,
        message="\u5df2\u52a0\u5165\u5bfc\u5165\u961f\u5217",
    )
    job_id = job["id"]
    thread = threading.Thread(target=_run_import_job, args=(job_id, pdf_path, toc_pages, pre_read, require_mineru, subject), daemon=True)
    thread.start()
    return {"success": True, "message": "\u6559\u6750\u5bfc\u5165\u4efb\u52a1\u5df2\u542f\u52a8", "job_id": job_id, "data": job}


@router.post("/import")
def import_book(
    file: UploadFile = File(...),
    toc_pages: str = Form(""),
    pre_read: bool = Form(False),
    subject: str = Form(""),
):
    return create_import_job(file=file, toc_pages=toc_pages, pre_read=pre_read, require_mineru=True, subject=subject)



@router.post("/import-mineru-output")
def import_mineru_output(
    file: UploadFile = File(...),
    book_name: str = Form(""),
    subject: str = Form(""),
):
    try:
        resolved_book = _safe_output_book_name(book_name or file.filename or "external_textbook")
        archive_path = _save_output_upload(file, resolved_book)
    except Exception as exc:
        return {"success": False, "message": str(exc)}

    job = _job_manager.create_job(
        IMPORT_JOB_TYPE,
        {
            "book_name": resolved_book,
            "file_path": str(archive_path),
            "require_mineru": False,
            "import_source": "external_mineru_output",
            "subject": normalize_subject_value(subject),
        },
        status="running",
        stage="queued",
        progress=0,
        message="External OCR output import queued",
    )
    job_id = job["id"]
    thread = threading.Thread(target=_run_output_import_job, args=(job_id, archive_path, resolved_book, subject), daemon=True)
    thread.start()
    return {"success": True, "message": "External OCR output import started", "job_id": job_id, "data": job}

@router.get("/import-jobs/{job_id}")
def get_import_job(job_id: str):
    job = _read_job(job_id)
    if not job:
        return {"success": False, "message": "\u672a\u627e\u5230\u5bfc\u5165\u4efb\u52a1"}
    return {"success": True, "data": job}


@router.post("/import-local")
def import_book_local(
    file: UploadFile = File(...),
    toc_pages: str = Form(""),
    subject: str = Form(""),
):
    try:
        pdf_path = _save_upload(file)
        result = import_textbook_local(pdf_path, pdf_path.stem, toc_pages=toc_pages)
        _save_chapters(pdf_path.stem, result.chapters)
        _write_book_meta(pdf_path.stem, subject=normalize_subject_value(subject))
        _set_current_book(pdf_path.stem, result.chapters, pdf_path)
        return {
            "success": True,
            "message": result.message,
            "data": {"name": pdf_path.stem, "subject": _book_subject(pdf_path.stem), "chapter_count": len(result.chapters), "used_mineru": False},
        }
    except Exception as exc:
        return {"success": False, "message": f"\u672c\u5730\u5bfc\u5165\u5931\u8d25\uff1a{exc}"}


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
        return {"success": False, "message": "\u8bf7\u5148\u9009\u62e9\u6559\u6750"}
    if len(chapters) < 2:
        return {"success": False, "message": "\u7ae0\u8282\u6570\u91cf\u4e0d\u8db3\uff0c\u65e0\u9700\u9884\u8bfb"}
    _start_pre_read(name, chapters, Path(pdf_path))
    return {"success": True, "message": f"\u9884\u8bfb\u5df2\u542f\u52a8 ({len(chapters)}\u7ae0)"}


@router.get("/preread/status")
def pre_read_status():
    bg = _book_state.get("bg_reader")
    if bg:
        status = bg.status
        if status.get("running"):
            return PreReadStatusOut(running=True, done=status.get("done", 0), total=status.get("total", 0), status_text=f"\u9884\u8bfb {status['done']}/{status['total']}")
        if status.get("done", 0) > 0:
            return PreReadStatusOut(running=False, done=status.get("done", 0), total=status.get("total", 0), status_text=f"\u5b8c\u6210 {status['done']}/{status['total']}")
    return PreReadStatusOut(status_text="")
