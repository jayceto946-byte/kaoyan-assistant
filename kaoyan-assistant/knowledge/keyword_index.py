"""关键词倒排索引 — 关键词 → 章节映射，自动溯源"""
import json
from pathlib import Path
from config import PROGRESS_PATH


class KeywordIndex:
    """关键词 → 章节倒排索引

    问 "KKT条件" → 索引命中 → 返回 "第3章 约束优化方法"
    """

    def __init__(self, book_name: str):
        self.file = Path(PROGRESS_PATH) / book_name / "keyword_index.json"
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, list[str]] = self._load()

    def _load(self) -> dict:
        if self.file.exists():
            with open(self.file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save(self):
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)

    def add_keywords(self, keywords: list[str], chapter: str):
        for kw in keywords:
            kw_lower = kw.lower().strip()
            if len(kw_lower) < 2:
                continue
            if kw_lower not in self._index:
                self._index[kw_lower] = []
            if chapter not in self._index[kw_lower]:
                self._index[kw_lower].append(chapter)
        self._save()

    def search(self, query: str) -> list[tuple[str, int]]:
        """搜索关键词，返回 [(章节名, 匹配数)]"""
        query_lower = query.lower()
        scores = {}
        for kw, chapters in self._index.items():
            if kw in query_lower or query_lower in kw:
                for ch in chapters:
                    scores[ch] = scores.get(ch, 0) + 1
        return sorted(scores.items(), key=lambda x: -x[1])

    def get_chapter_keywords(self, chapter: str) -> list[str]:
        return [kw for kw, chs in self._index.items() if chapter in chs]

    def total_terms(self) -> int:
        return len(self._index)
