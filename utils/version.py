"""Application version loaded from the repository/package VERSION file."""
from __future__ import annotations

from pathlib import Path


def _read_version() -> str:
    version_path = Path(__file__).resolve().parents[1] / "VERSION"
    try:
        value = version_path.read_text(encoding="utf-8").strip()
    except OSError:
        value = "1.0.0"
    return value or "1.0.0"


APP_VERSION = _read_version()
