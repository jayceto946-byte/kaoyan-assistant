"""章节摘要库 — 预生成摘要/重点/思维导图，避免重复计算"""
import json
from pathlib import Path
from config import PROGRESS_PATH


class SummaryStore:
    """章节摘要缓存

    每章存储：
    - summary: 文字总结
    - key_points: 重点列表
    - teaching: 讲解摘要
    - generated_at: 生成时间
    """

    def __init__(self, book_name: str):
        self.file = Path(PROGRESS_PATH) / book_name / "chapter_summaries.json"
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self._store = self._load()

    def _load(self) -> dict:
        if self.file.exists():
            with open(self.file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save(self):
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(self._store, f, ensure_ascii=False, indent=2)

    def get(self, chapter: str) -> dict | None:
        """获取缓存摘要"""
        return self._store.get(chapter)

    def set(self, chapter: str, data: dict):
        """写入摘要"""
        import datetime
        data["generated_at"] = datetime.datetime.now().isoformat()
        self._store[chapter] = data
        self._save()

    def get_all(self) -> dict:
        return self._store

    def list_chapters(self) -> list[str]:
        return list(self._store.keys())

    def clear(self):
        self._store = {}
        self._save()
