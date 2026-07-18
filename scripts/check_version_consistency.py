"""Fail when release-facing version declarations differ from VERSION."""
from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    expected = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", expected):
        raise SystemExit(f"Invalid VERSION value: {expected!r}")
    declared = {
        "frontend/package.json": json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))["version"],
        "desktop/package.json": json.loads((ROOT / "desktop/package.json").read_text(encoding="utf-8"))["version"],
    }
    for relative in ("frontend/package-lock.json", "desktop/package-lock.json"):
        lock = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        declared[relative] = lock.get("packages", {}).get("", {}).get("version") or lock.get("version")
    mismatches = {path: value for path, value in declared.items() if value != expected}
    if mismatches:
        details = ", ".join(f"{path}={value}" for path, value in mismatches.items())
        raise SystemExit(f"Version mismatch: VERSION={expected}; {details}")
    print(f"Version consistency OK: {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
