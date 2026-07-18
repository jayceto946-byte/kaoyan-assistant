"""Set the product version in VERSION and package manifests."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("version", help="Semantic version, for example 1.0.1")
    args = parser.parse_args()
    version = args.version.strip().lstrip("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", version):
        parser.error("version must be a semantic version such as 1.0.1")
    (ROOT / "VERSION").write_text(version + "\n", encoding="utf-8")
    for relative in ("frontend/package.json", "desktop/package.json"):
        path = ROOT / relative
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["version"] = version
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for relative in ("frontend/package-lock.json", "desktop/package-lock.json"):
        path = ROOT / relative
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["version"] = version
        payload.setdefault("packages", {}).setdefault("", {})["version"] = version
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Product version set to {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
