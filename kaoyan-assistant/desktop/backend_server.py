"""Packaged FastAPI entrypoint for the Electron desktop shell."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import uvicorn


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[1]


def _seed_sample_data(data_dir: Path) -> None:
    sample_dir = Path(os.getenv("KAOYAN_SEED_DATA_DIR", ""))
    if not sample_dir:
        sample_dir = _bundle_root() / "sample_data"
    if not sample_dir.exists():
        return

    real_files = [p for p in sample_dir.rglob("*") if p.is_file() and p.name not in {".gitkeep", "README.md"}]
    if not real_files:
        return

    marker = data_dir / ".sample_data_seeded"
    if marker.exists():
        return

    data_dir.mkdir(parents=True, exist_ok=True)
    for src in real_files:
        rel = src.relative_to(sample_dir)
        dest = data_dir / rel
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    marker.write_text("seeded\n", encoding="utf-8")


def main() -> None:
    root = _bundle_root()
    os.chdir(root)

    data_dir = Path(os.getenv("DATA_DIR", root / "data"))
    os.environ.setdefault("DATA_DIR", str(data_dir))
    os.environ.setdefault("ENV_PATH", str(data_dir.parent / ".env"))
    os.environ.setdefault("MINERU_OUTPUT_PATH", str(data_dir.parent / "mineru_output"))
    os.environ.setdefault("SKIP_VECTOR_WARMUP", "1")
    os.environ.setdefault("SKIP_EMBEDDING_WARMUP", "1")
    os.environ.setdefault("EMBEDDING_LOCAL_FILES_ONLY", "1")

    _seed_sample_data(data_dir)

    port = int(os.getenv("KAOYAN_BACKEND_PORT", "8000"))
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=port,
        reload=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
