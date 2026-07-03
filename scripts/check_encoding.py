"""Audit project text files for likely encoding problems."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

EXCLUDE_DIRS = {
    ".git", ".agents", ".codex", "node_modules", "dist", "release", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".next", "venv", "venv310", "venv312",
    "data", "exports", "build", "htmlcov", ".ruff_cache", "models", "vector_db",
}
TEXT_EXTS = {
    ".py", ".tsx", ".ts", ".js", ".jsx", ".cjs", ".mjs", ".css", ".html",
    ".md", ".json", ".yml", ".yaml", ".txt", ".ps1", ".sh", ".toml",
    ".ini", ".cfg", ".example", ".env", ".dockerfile",
}
TEXT_NAMES = {"Dockerfile", ".env.example", "AGENTS.md", "README.md", "pytest.ini"}
MOJIBAKE_TOKENS = [
    "\u951b", "\u7ed4", "\u9422", "\u6d93\u20ac", "\u6d93", "\u935a",
    "\u699b", "\u5bb8", "\u93c3", "\u7441", "\u93b5", "\u95bf",
    "\u68f0", "\u7039", "\u9365", "\u9366", "\u934f", "\u7487",
    "\u6d60", "\u9a9e", "\u6dc7", "\u9234", "\u4e63", "\u4e7c",
    "\u4e75", "\u053d\u037c",
]
QUESTION_RE = re.compile(r"\?{3,}")
REPLACEMENT_RE = re.compile("\ufffd")
CP1252_RE = re.compile(r"(?:\u00e2[\u0080-\u00bf]|\u00c3[\u0080-\u00bf]|\u00e4\u00b8|\u00e5[\u0080-\u00bf]|\u00e7[\u0080-\u00bf])")


def should_scan(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    if path.name == "encoding_audit_report.json":
        return False
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return False
    return path.suffix.lower() in TEXT_EXTS or path.name in TEXT_NAMES


def audit(root: Path) -> dict:
    invalid = []
    bom = []
    suspicious = []
    scanned = 0
    for path in root.rglob("*"):
        if not path.is_file() or not should_scan(path, root):
            continue
        rel = path.relative_to(root).as_posix()
        try:
            data = path.read_bytes()
        except Exception as exc:
            invalid.append({"file": rel, "error": f"read failed: {exc}"})
            continue
        if b"\x00" in data[:4096]:
            continue
        scanned += 1
        if data.startswith(b"\xef\xbb\xbf"):
            bom.append(rel)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            invalid.append({"file": rel, "error": str(exc)})
            continue
        hits = [(token, text.count(token)) for token in MOJIBAKE_TOKENS if text.count(token)]
        q_count = len(QUESTION_RE.findall(text))
        repl_count = len(REPLACEMENT_RE.findall(text))
        cp_count = len(CP1252_RE.findall(text))
        if not (hits or q_count or repl_count or cp_count):
            continue
        samples = []
        for idx, line in enumerate(text.splitlines(), 1):
            if len(samples) >= 6:
                break
            if any(token in line for token, _ in hits) or QUESTION_RE.search(line) or REPLACEMENT_RE.search(line) or CP1252_RE.search(line):
                samples.append({"line": idx, "text": line[:220]})
        score = sum(count for _, count in hits) + q_count * 8 + repl_count * 20 + cp_count * 5
        suspicious.append({
            "file": rel,
            "score": score,
            "hits": hits,
            "question_runs": q_count,
            "replacement_chars": repl_count,
            "cp1252_like": cp_count,
            "samples": samples,
        })
    suspicious.sort(key=lambda item: item["score"], reverse=True)
    return {"scanned_files": scanned, "invalid_utf8": invalid, "bom_files": bom, "suspicious_files": suspicious}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", default="encoding_audit_report.json")
    parser.add_argument("--fail-on-issues", action="store_true")
    args = parser.parse_args()
    report = audit(Path(args.root).resolve())
    Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"scanned_files={report['scanned_files']}")
    print(f"invalid_utf8={len(report['invalid_utf8'])}")
    print(f"bom_files={len(report['bom_files'])}")
    print(f"suspicious_files={len(report['suspicious_files'])}")
    for item in report["suspicious_files"][:20]:
        print(f"- {item['file']} score={item['score']} q={item['question_runs']} repl={item['replacement_chars']}")
    if args.fail_on_issues and (report["invalid_utf8"] or report["bom_files"] or report["suspicious_files"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
