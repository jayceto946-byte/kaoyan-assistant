"""后台预读 — 导入后静默按章阅读全文 + 建立关键词索引"""
import json
import threading
from pathlib import Path

from config import BOOKS_PATH, PROGRESS_PATH


class BackgroundReader:
    """后台线程按 TOC 精确页码预读所有章节"""

    def __init__(self, book_name: str, chapters: list[dict], pdf_path: Path):
        self.book_name = book_name
        self.chapters = chapters
        self.pdf_path = pdf_path
        self.progress_file = Path(PROGRESS_PATH) / book_name / "_bg_read_progress.json"
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        self._thread = None
        self._running = False

    @property
    def status(self) -> dict:
        try:
            if self.progress_file.exists():
                with open(str(self.progress_file), "r", encoding="utf-8", errors="replace") as f:
                    return json.loads(f.read())
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        return {"done": 0, "total": len(self.chapters), "current": "", "running": False}

    def _save_status(self, **kwargs):
        st = {"done": 0, "total": len(self.chapters), "current": "", "running": self._running}
        st.update(kwargs)
        with open(str(self.progress_file), "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)

    def start(self):
        if self._running:
            return
        self._running = True
        self._save_status()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        done = 0
        final_current = "\u5b8c\u6210"
        error = ""
        try:
            from ingestion.kimi_reader import KimiReader
            from knowledge.keyword_index import KeywordIndex

            reader = KimiReader(self.book_name)
            kw_index = KeywordIndex(self.book_name)
            for ch in self.chapters:
                if not self._running:
                    final_current = "\u5df2\u505c\u6b62"
                    break
                title = ch.get("title", f"Ch{done+1}")
                start = max(0, ch.get("page_number", 1) - 1)
                end = ch.get("end_page", start + 10)
                self._save_status(done=done, current=title)
                try:
                    text, kws = reader.read_pages(
                        self.pdf_path, start, end, title, extract_keywords=True
                    )
                    if kws:
                        kw_index.add_keywords(kws, title)
                except Exception as exc:
                    print(f"[preread] {title} failed: {exc}", flush=True)
                done += 1
        except Exception as exc:
            error = str(exc)
            final_current = "\u5931\u8d25"
            print(f"[preread] worker failed: {exc}", flush=True)
        finally:
            self._running = False
            try:
                self._save_status(done=done, current=final_current, running=False, error=error)
            except Exception as exc:
                print(f"[preread] failed to persist final status: {exc}", flush=True)
