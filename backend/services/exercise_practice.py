"""Application service for exercise practice-session workflows."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Callable


RecordPayload = Callable[[Any], dict]
MistakeFactory = Callable[..., Any]
EventLogger = Callable[[str, Any, dict], None]


@dataclass
class ExercisePracticeService:
    bank: Any
    book_name: str
    mistake_book_factory: Callable[[], Any]
    record_payload: RecordPayload
    mistake_factory: MistakeFactory
    log_event: EventLogger

    def session_data(self, session: Any) -> dict:
        data = session.to_dict()
        current = self.bank.current_session_record(session)
        data["current_exercise"] = self.record_payload(current) if current else None
        data["summary"] = session.summary()
        return data

    def create_session(self, request: Any) -> dict:
        try:
            session = self.bank.create_practice_session(
                subject=request.subject,
                chapter=request.chapter,
                tag=request.tag,
                status=request.status,
                limit=request.limit,
                shuffle=request.shuffle,
            )
            return {
                "success": True,
                "data": self.session_data(session),
                "message": "练习会话已开始",
            }
        except ValueError as exc:
            return {"success": False, "message": str(exc)}

    def active_session(self) -> dict:
        session = self.bank.get_active_practice_session()
        return {
            "success": True,
            "data": self.session_data(session) if session else None,
        }

    def get_session(self, session_id: str) -> dict:
        session = self.bank.get_practice_session(session_id)
        if not session:
            return {"success": False, "message": "未找到练习会话"}
        return {"success": True, "data": self.session_data(session)}

    def answer_session(self, session_id: str, request: Any) -> dict:
        try:
            session, record, answer_created = self.bank.record_session_answer_with_status(
                session_id,
                exercise_id=request.exercise_id,
                user_answer=request.user_answer,
                quality=request.quality,
                note=request.note,
            )
        except ValueError as exc:
            return {"success": False, "message": str(exc)}

        mistake_id = str(session.results.get(record.id, {}).get("mistake_id") or "")
        if request.add_to_mistake and not mistake_id:
            stable_key = f"{self.book_name}\0{session_id}\0{record.id}"
            stable_mistake_id = (
                "ps_" + hashlib.sha256(stable_key.encode("utf-8")).hexdigest()[:16]
            )
            try:
                mistake_id = self.mistake_book_factory().add_if_absent(
                    self.mistake_factory(
                        record,
                        user_answer=request.user_answer,
                        mistake_id=stable_mistake_id,
                    )
                )
                session = self.bank.attach_practice_session_mistake(
                    session_id,
                    record.id,
                    mistake_id,
                )
            except Exception as exc:
                return {
                    "success": False,
                    "message": f"作答已记录，但写入错题本失败，可重试：{exc}",
                    "retryable": True,
                    "data": self.session_data(session),
                    "record": self.record_payload(record),
                }
            self.log_event(
                "exercise_to_mistake",
                record,
                {
                    "mistake_id": mistake_id,
                    "trigger": "practice_session",
                    "session_id": session_id,
                },
            )
        if answer_created:
            self.log_event(
                "exercise_practiced",
                record,
                {
                    "quality": request.quality,
                    "status": record.status,
                    "session_id": session_id,
                },
            )
        message = "本轮练习已完成" if session.status == "completed" else "已记录，进入下一题"
        return {
            "success": True,
            "data": self.session_data(session),
            "record": self.record_payload(record),
            "mistake_id": mistake_id,
            "message": message,
        }

    def change_status(self, session_id: str, status: str) -> dict:
        try:
            session = self.bank.set_practice_session_status(session_id, status)
            return {"success": True, "data": self.session_data(session)}
        except ValueError as exc:
            return {"success": False, "message": str(exc)}
