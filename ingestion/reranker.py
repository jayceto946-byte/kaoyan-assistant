"""Optional local cross-encoder reranker with a safe no-model fallback."""
from __future__ import annotations

import os
from pathlib import Path

_model = None
_attempted = False


def _get_model():
    global _model, _attempted
    if _attempted:
        return _model
    _attempted = True
    model_path = os.getenv("RERANKER_MODEL_PATH", "").strip()
    if not model_path or not Path(model_path).exists():
        return None
    try:
        from sentence_transformers import CrossEncoder
        _model = CrossEncoder(model_path, device=os.getenv("RERANKER_DEVICE", "cpu"), local_files_only=True)
    except Exception as exc:
        print(f"[reranker] local model unavailable, using deterministic rerank: {exc}", flush=True)
        _model = None
    return _model


def cross_encoder_scores(query: str, texts: list[str]) -> list[float] | None:
    model = _get_model()
    if model is None or not texts:
        return None
    try:
        values = model.predict([(query, text) for text in texts], show_progress_bar=False)
        return [float(value) for value in values]
    except Exception as exc:
        print(f"[reranker] scoring failed, using deterministic rerank: {exc}", flush=True)
        return None


def reranker_status() -> dict:
    configured = bool(os.getenv("RERANKER_MODEL_PATH", "").strip())
    return {
        "configured": configured,
        "active": _model is not None,
        "mode": "cross_encoder" if _model is not None else "deterministic",
    }
