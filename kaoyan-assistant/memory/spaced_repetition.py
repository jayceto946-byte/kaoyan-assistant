"""间隔重复模块 - 基于SM-2算法的智能复习调度"""
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from config import PROGRESS_PATH


class SpacedRepetition:
    """SM-2算法：管理知识点的复习间隔"""

    def __init__(self, book_name: str):
        self.base_path = Path(PROGRESS_PATH) / book_name
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.file = self.base_path / "spaced_repetition.json"
        self._cards: dict[str, dict] = self._load()
        # card: {chapter, knowledge_point, easiness, interval, reps, next_review, last_review}

    def _load(self) -> dict:
        if self.file.exists():
            with open(self.file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save(self):
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(self._cards, f, ensure_ascii=False, indent=2)

    def add_knowledge_point(self, card_id: str, chapter: str, knowledge_point: str):
        """添加知识点卡片"""
        if card_id not in self._cards:
            self._cards[card_id] = {
                "chapter": chapter,
                "knowledge_point": knowledge_point,
                "easiness": 2.5,
                "interval": 1,
                "repetitions": 0,
                "next_review": date.today().isoformat(),
                "last_review": None,
            }
            self._save()

    def review(self, card_id: str, quality: int):
        """复习知识点并更新间隔

        Args:
            quality: 0(完全不记得) ~ 5(完美掌握)
        """
        card = self._cards.get(card_id)
        if not card:
            return

        card["last_review"] = date.today().isoformat()

        if quality >= 3:
            if card["repetitions"] == 0:
                card["interval"] = 1
            elif card["repetitions"] == 1:
                card["interval"] = 6
            else:
                card["interval"] = int(round(card["interval"] * card["easiness"]))

            card["repetitions"] += 1
        else:
            card["repetitions"] = 0
            card["interval"] = 1

        card["easiness"] = max(
            1.3,
            card["easiness"] + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02),
        )

        card["next_review"] = (
            date.today() + timedelta(days=max(1, card["interval"]))
        ).isoformat()

        self._save()

    def auto_review_from_quiz(self, chapter: str, knowledge_point: str,
                              score: int, out_of: int = 100):
        """从答题结果自动映射到SM-2质量评分"""
        if out_of <= 0:
            return
        pct = score / out_of
        if pct >= 0.9:
            quality = 5
        elif pct >= 0.8:
            quality = 4
        elif pct >= 0.6:
            quality = 3
        elif pct >= 0.4:
            quality = 2
        elif pct >= 0.2:
            quality = 1
        else:
            quality = 0

        card_id = f"{chapter}::{knowledge_point}"
        if card_id not in self._cards:
            self.add_knowledge_point(card_id, chapter, knowledge_point)
        self.review(card_id, quality)

    def get_due_reviews(self) -> list[dict]:
        """获取今日待复习的知识点"""
        today = date.today().isoformat()
        due = []
        for card_id, card in self._cards.items():
            if card["next_review"] <= today:
                due.append({
                    "card_id": card_id,
                    "chapter": card["chapter"],
                    "knowledge_point": card["knowledge_point"],
                    "easiness": card["easiness"],
                    "interval": card["interval"],
                    "repetitions": card["repetitions"],
                    "last_review": card.get("last_review"),
                })
        return sorted(due, key=lambda c: c["easiness"])

    def get_chapter_due(self, chapter: str) -> list[dict]:
        """获取指定章节待复习的知识点"""
        return [c for c in self.get_due_reviews() if c["chapter"] == chapter]

    def get_stats(self) -> dict:
        """获取间隔重复统计"""
        total = len(self._cards)
        if total == 0:
            return {"total": 0, "due_today": 0, "mastered": 0, "learning": 0}

        due = len(self.get_due_reviews())
        mastered = sum(1 for c in self._cards.values() if c["interval"] >= 21)
        return {
            "total": total,
            "due_today": due,
            "mastered": mastered,
            "learning": total - mastered,
        }

    def get_weekly_schedule(self) -> dict[str, int]:
        """获取未来7天每日待复习数量"""
        schedule = {}
        today = date.today()
        for i in range(7):
            d = (today + timedelta(days=i)).isoformat()
            count = sum(
                1 for c in self._cards.values()
                if c["next_review"] <= d
            )
            schedule[d] = count
        return schedule
