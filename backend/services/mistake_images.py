"""Filesystem lifecycle for mistake-image uploads."""
from __future__ import annotations

import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MistakeImageStore:
    images_path: Path
    allowed_extensions: frozenset[str]
    max_image_bytes: int
    ocr_max_side: int
    ocr_jpeg_quality: int
    pending_max_age_seconds: int

    @property
    def image_root(self) -> Path:
        return self.images_path / "mistakes"

    @property
    def pending_root(self) -> Path:
        return self.image_root / "pending"

    def delete(self, path: str | Path | None) -> None:
        """Delete only files that resolve inside the managed image root."""
        if not path:
            return
        candidate = Path(path).resolve()
        root = self.image_root.resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return
        candidate.unlink(missing_ok=True)

    def cleanup_stale_pending(self) -> None:
        pending = self.pending_root
        if not pending.exists():
            return
        cutoff = time.time() - self.pending_max_age_seconds
        for path in pending.iterdir():
            try:
                if path.is_file() and path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
            except OSError:
                continue

    def commit_pending(self, path: str | None) -> tuple[str | None, bool]:
        if not path:
            return None, False
        source = Path(path).resolve()
        root = self.image_root.resolve()
        pending = self.pending_root.resolve()
        try:
            source.relative_to(root)
        except ValueError:
            raise ValueError("图片路径不在错题图片目录内")
        if not source.exists() or not source.is_file():
            raise ValueError("待保存图片不存在")
        try:
            source.relative_to(pending)
        except ValueError:
            return str(source), False

        root.mkdir(parents=True, exist_ok=True)
        destination = root / source.name
        if destination.exists():
            destination = root / f"{uuid.uuid4().hex}_{source.name}"
        shutil.move(str(source), str(destination))
        return str(destination), True

    def save_upload(self, file: Any) -> Path:
        filename = file.filename or "mistake.png"
        suffix = Path(filename).suffix.lower()
        if suffix not in self.allowed_extensions:
            raise ValueError("请上传 png/jpg/jpeg/webp/bmp 格式的图片")

        self.cleanup_stale_pending()
        self.pending_root.mkdir(parents=True, exist_ok=True)
        raw_path = self.pending_root / f"{uuid.uuid4().hex}_raw{suffix}"

        size = 0
        with open(raw_path, "wb") as handle:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > self.max_image_bytes:
                    handle.close()
                    raw_path.unlink(missing_ok=True)
                    raise ValueError("图片不能超过 20MB")
                handle.write(chunk)
        return self.optimize_for_ocr(raw_path)

    def optimize_for_ocr(self, raw_path: Path) -> Path:
        optimized_path = raw_path.with_name(
            raw_path.stem.replace("_raw", "") + "_ocr.jpg"
        )
        try:
            from PIL import Image, ImageOps

            with Image.open(raw_path) as image:
                image = ImageOps.exif_transpose(image)
                if image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")
                width, height = image.size
                scale = min(1.0, self.ocr_max_side / max(width, height))
                if scale < 1.0:
                    next_size = (
                        max(1, int(width * scale)),
                        max(1, int(height * scale)),
                    )
                    image = image.resize(next_size, Image.Resampling.LANCZOS)
                if image.mode == "L":
                    image = image.convert("RGB")
                image.save(
                    optimized_path,
                    format="JPEG",
                    quality=self.ocr_jpeg_quality,
                    optimize=True,
                )
            raw_path.unlink(missing_ok=True)
            return optimized_path
        except Exception:
            optimized_path.unlink(missing_ok=True)
            return raw_path
