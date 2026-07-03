"""HTTP client for an external MinerU 3.x API service.

The main app does not import MinerU runtime packages. MinerU can run on a
local GPU box, a rented GPU machine, or another Docker service.
"""
from __future__ import annotations

import json
import time
import zipfile
from pathlib import Path
from typing import Any, Callable

import httpx


class MinerUClientError(RuntimeError):
    pass


class MinerUClient:
    def __init__(self, base_url: str, timeout: float = 120):
        if not base_url:
            raise MinerUClientError("MINERU_API_URL is not configured")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def submit_pdf(self, pdf_path: Path, **options: Any) -> str:
        data = {
            "return_md": "true",
            "response_format_zip": "true",
            "return_original_file": "false",
        }
        for key, value in options.items():
            if value is not None:
                data[key] = str(value).lower() if isinstance(value, bool) else str(value)

        with httpx.Client(timeout=self.timeout, trust_env=False) as client:
            with open(pdf_path, "rb") as fh:
                files = {"files": (pdf_path.name, fh, "application/pdf")}
                resp = client.post(f"{self.base_url}/tasks", data=data, files=files)
            resp.raise_for_status()
            payload = resp.json()
        task_id = self._extract_task_id(payload)
        if not task_id:
            raise MinerUClientError(f"MinerU did not return task_id: {payload}")
        return task_id

    def task_status(self, task_id: str) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout, trust_env=False) as client:
            resp = client.get(f"{self.base_url}/tasks/{task_id}")
            resp.raise_for_status()
            return resp.json()

    def wait_for_task(
        self,
        task_id: str,
        timeout_seconds: int,
        poll_seconds: float,
        on_progress: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        started = time.time()
        last_state = ""
        while True:
            payload = self.task_status(task_id)
            state = self._extract_state(payload)
            if on_progress and state != last_state:
                on_progress(state, payload)
                last_state = state
            if state in {"completed", "complete", "done", "finished", "success", "succeeded"}:
                return payload
            if state in {"failed", "error", "cancelled", "canceled"}:
                raise MinerUClientError(f"MinerU task failed: {payload}")
            if time.time() - started > timeout_seconds:
                raise MinerUClientError(f"MinerU task timed out after {timeout_seconds}s: {payload}")
            time.sleep(poll_seconds)

    def fetch_result(self, task_id: str, output_dir: Path) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        with httpx.Client(timeout=self.timeout, trust_env=False) as client:
            resp = client.get(f"{self.base_url}/tasks/{task_id}/result")
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            body = resp.content

        if "zip" in content_type or body.startswith(b"PK"):
            zip_path = output_dir / f"{task_id}.zip"
            zip_path.write_bytes(body)
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(output_dir)
            return {"type": "zip", "path": str(zip_path)}

        try:
            payload = resp.json()
        except json.JSONDecodeError:
            raw_path = output_dir / f"{task_id}_result.bin"
            raw_path.write_bytes(body)
            return {"type": "raw", "path": str(raw_path), "content_type": content_type}

        result_path = output_dir / f"{task_id}_result.json"
        result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"type": "json", "path": str(result_path), "payload": payload}

    @staticmethod
    def _extract_task_id(payload: dict[str, Any]) -> str:
        for key in ("task_id", "id"):
            if payload.get(key):
                return str(payload[key])
        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("task_id", "id"):
                if data.get(key):
                    return str(data[key])
        return ""

    @staticmethod
    def _extract_state(payload: dict[str, Any]) -> str:
        for key in ("status", "state", "task_status"):
            if payload.get(key):
                return str(payload[key]).lower()
        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("status", "state", "task_status"):
                if data.get(key):
                    return str(data[key]).lower()
        return "running"
