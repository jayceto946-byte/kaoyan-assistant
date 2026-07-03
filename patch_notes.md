# Patch Notes - Kaoyan Assistant

This file records version changes, bug fixes, migration notes, validation results, and environment repair records.

Note: Earlier historical entries contained mojibake from an encoding mismatch. Those damaged details were compressed on 2026-07-03 instead of being guessed back into Chinese text. For long-term constraints and architecture, use `AGENTS.md`.

---

## 2026-07-03 - Stage closeout cleanup

- Cleaned `patch_notes.md` so the file is UTF-8 readable and no longer carries historical mojibake blocks.
- Kept this file focused on durable release notes and validation results; unstable or damaged historical prose was replaced with this explicit note.

### Validation

- `./venv310/Scripts/python.exe -m pytest -q` passed: `59 passed, 3 warnings`.
- `./venv310/Scripts/python.exe -B scripts/check_encoding.py --json encoding_audit_report.json --fail-on-issues` passed: `invalid_utf8=0`, `bom_files=0`, `suspicious_files=0`.
- `npm.cmd run lint` completed with no errors and one existing React hooks dependency warning in `HighlightRepositoryDialog.tsx`.
- `npm.cmd test` passed outside the Windows sandbox after the sandboxed run hit `spawn EPERM`: `2 passed`, `7 passed`.
- `npm.cmd run build` passed.

---

## 2026-07-03 - Controlled Learning Tool Registry

- Added `backend/tools/` with a controlled tool registry for textbook search, concept search/linking, due mistakes, mistake stats, review-plan building, and confirmation-only write proposals.
- Added `/api/agent/tools`, `/api/agent/tools/call`, and `/api/agent/read-only` as the first read-only agent orchestration surface.
- Mounted the new agent router in `backend/main.py`.
- Added frontend API client helpers and TypeScript response types for listing tools, calling a tool, and running the read-only agent.

### Validation

- `python -m pytest tests/test_agent_tools.py -q` passed in the original feature run.
- Importing `backend.main.app` confirmed `/api/agent/read-only` was registered.

---

## 2026-07-03 - Read-only agent frontend entry points

- Connected the controlled read-only agent to chat quick workflows for today's review plan and recent weak-point/mistake analysis.
- Added `AgentResultCard` to show synthesized answers, collapsed tool evidence, and confirmation-only pending actions.
- Added an AI review-plan action to the Learning page header.

### Validation

- `npm.cmd run build` passed in the original feature run.
- `python -B -m pytest tests/test_agent_tools.py -q` passed in the original feature run.

---

## 2026-07-03 - Project encoding audit

- Added `scripts/check_encoding.py` to scan project text files for UTF-8 decode failures, BOMs, replacement characters, long question-mark runs, and common Chinese mojibake fragments.
- Removed UTF-8 BOM noise from source and documentation files.
- Fixed mojibake in `memory/exercise_importer.py` prompt text, `knowledge/concept_memory.py` docstrings, and affected tests.
- Recorded that `patch_notes.md` was the only remaining suspicious file before this cleanup.

### Validation

- `python -B scripts/check_encoding.py --json encoding_audit_report.json` previously reported `invalid_utf8=0`, `bom_files=0`, and `suspicious_files=1` for `patch_notes.md`.
- The closeout run should regenerate this report after the cleanup.

---

## 2026-07-03 - Chapter highlight repository task state and compact layout

- Fixed chapter-highlight repository progress so background-generation state only appears for the matching selected book, chapter, section, and job target.
- Bound highlight jobs to a concrete generation scope and surfaced completion prompts that jump to the generated highlight result.
- Moved the highlight repository dialog to a portal attached to `document.body`, improving compact-window and Electron layout behavior.
- Lowered the Electron desktop minimum window size to `720x560` to support compact layout verification.

### Validation

- `npm.cmd run build` passed in the original feature run.
- Full-chapter highlight generation remained serial by section; this is still the primary latency point.

---

## 2026-07-03 - Mistake image crop interaction

- Reworked mistake-image capture cropping from numeric sliders into a draggable selection rectangle on the image.
- Added drag-to-move, eight edge/corner resize handles, and drag-to-create region selection.
- Preserved brightness, contrast, sharpening, and black-white scan tuning controls.

### Validation

- `npm.cmd run build` passed in the original feature run.

---

## 2026-07-03 - Chapter highlight background task behavior

- Fixed chat quick actions so background chapter-highlight generation no longer blocks unrelated chat workflows.
- Added duplicate-scope reuse and serial execution for chapter-highlight background jobs.
- Reduced extra LLM repair calls by preferring local LaTeX cleanup and validation before one optional formula repair pass.
- Reviewed other long-task paths: textbook import and external OCR import already run as background jobs; mistake OCR/solve, reports, and random practice remain local synchronous actions.

### Validation

- `npm.cmd run build` passed in the original feature run.
- Import checks for `ChapterHighlightService` and `HighlightJobStore` passed in the original feature run.

---

## 2026-07-02 - Study cockpit, book management, and highlight background tasks

- Added a richer chat home panel with current subject/textbook context, due-mistake review, weak-concept review, random exercise, highlight, report, and quick mistake capture actions.
- Added settings-center textbook management so imported books can have their subject corrected and can be set as the current chat book without renaming paths or touching indexes.
- Added `PATCH /api/books/{book_name}` for safe textbook metadata updates.
- Added chapter-highlight deletion for generated artifacts.
- Adjusted exercise Word/PDF import copy to clarify that low-confidence repair uses the text LLM backend by default.

### Validation

- `./venv310/Scripts/python.exe -m pytest -q` passed in the original feature run: `56 passed, 3 warnings`.
- `npm.cmd run build` passed.
- `npm.cmd run lint` passed.
- `npm.cmd test` passed after rerunning outside the Windows sandbox EPERM.

---

## 2026-07-02 - Chapter highlight split and frontend lazy rendering

- Split `knowledge/chapter_highlights.py` into focused modules for source assembly, LLM generation, LaTeX validation/repair, artifact writing, shared types/constants, and background job management.
- Preserved public imports for `ChapterHighlightService`, `ChapterHighlightError`, `PROMPT_VERSION`, and `HighlightJobStore`.
- Lazy-loaded rich Markdown/KaTeX rendering through `MarkdownRenderer.tsx`.
- Added `useVisibleList()` and applied client-side pagination to long exercise and mistake lists.
- Extracted settings health polling into `useSystemHealth()`.

### Validation

- `./venv310/Scripts/python.exe -B -m pytest tests/test_generator.py tests/test_job_manager_and_roles.py -q` passed in the original feature run: `15 passed`.
- `./venv310/Scripts/python.exe -B -m pytest -q` passed in the original feature run: `56 passed, 3 warnings`.
- `npm.cmd run build` passed.
- `npm.cmd run lint -- --no-cache` passed.

---

## 2026-07-02 - Retrieval isolation and main workflow hardening

- Scoped new Chroma collections by `book_name + chapter_title`, with legacy chapter-only collections still readable as fallback.
- Rebuilt target scoped collections before writing new documents to prevent duplicates and stale chunks.
- Passed active `book_name` into planner, retrieval, chapter teaching, and mistake explanation RAG calls.
- Added safe vector-store adapters so Chroma failures degrade instead of breaking user-facing flows.
- Fixed chat quick mistake capture book loading, textbook import polling cleanup, external OCR output copy, and chat stop behavior.
- Lazy-loaded frontend route bundles.

### Validation

- `./venv310/Scripts/python.exe -m pytest tests/test_job_manager_and_roles.py tests/test_external_mineru_output_import.py tests/test_rag_degradation.py tests/test_chat_stream_reliability.py -q` passed in the original feature run: `13 passed, 3 warnings`.
- `./venv310/Scripts/python.exe -m pytest -q` passed in the original feature run: `56 passed, 3 warnings`.
- `npm.cmd run build` passed.
- `npm.cmd run lint -- --no-cache` passed.

---

## 2026-07-01 - External OCR output import path

- Added `import_textbook_from_mineru_output()` for workflows where MinerU runs on another machine and the desktop app only builds local chapters and Chroma indexes.
- Added `POST /api/books/import-mineru-output` for safe zip uploads with path traversal checks.
- Changed book listing/switching so externally imported books can appear and be selected without a local source PDF.
- Exposed `MINERU_API_URL` as the recommended external-service path and kept local MinerU CLI as advanced configuration.

### Validation

- `./venv310/Scripts/python.exe -m pytest tests/test_external_mineru_output_import.py -q` passed in the original feature run: `2 passed`.
- `./venv310/Scripts/python.exe -m pytest -q` passed in the original feature run: `55 passed, 3 warnings`.
- `npm.cmd run build` passed.
- `npm.cmd run lint -- --no-cache` passed.

---

## 2026-07-01 - Exercise import LLM repair and release lock

- Changed `memory/exercise_importer.py` to produce scored candidate splits before labeling.
- Added optional low-confidence LLM repair for uncertain exercise-import blocks while keeping the rule pipeline as the default.
- Added `split_confidence`, `split_reasons`, `refined_by_llm`, and `summary.llm_refined` to exercise analysis responses.
- Added `requirements-release.txt` as a release-only pinned backend/build dependency set.
- Updated the desktop backend build script to exclude legacy agents, OCR runtimes, and extra data-science/dev packages.

### Validation

- `./venv310/Scripts/python.exe -m pytest tests/test_exercise_importer.py tests/test_exercise_file_importer.py -q` passed in the original feature run: `5 passed, 3 warnings`.
- `./venv310/Scripts/python.exe -m pytest -q` passed in the original feature run: `53 passed, 3 warnings`.
- `npm.cmd run build` passed.
- `npm.cmd run lint -- --no-cache` passed.

---

## 2026-07-01 - Learning event log and packaging trim

- Added `memory/learning_events.py`, a SQLite append-only timeline for chat QA, concept exposure/candidates, mistakes, and exercise actions.
- Added `book_name`, `subject`, and `conversation_id` plumbing to concept exposure and chat graph state.
- Changed mistake and exercise APIs to write best-effort learning events for add/review/explain/practice/import/transfer actions.
- Trimmed the desktop PyInstaller build by excluding retired UI/dev packages.

### Validation

- Backend tests and frontend build passed in the original feature run.

---

## 2026-06-23 to 2026-06-30 - Historical compressed notes

The detailed historical notes for this period were damaged by mojibake before this cleanup. The reliable high-level record is:

- Added and iterated the exercise bank, including manual entry, Word/PDF import, rule-based candidate splitting, batch add, status updates, and mistake/exercise transfer flows.
- Added mistake image OCR/solve workflows, Kimi Vision OCR configuration, image preprocessing, and SM-2 review improvements.
- Hardened streaming chat, including SSE stage ordering, frontend accumulation safety under React StrictMode, long-answer rendering fallback, LaTeX sanitization, and ASGI error conversion.
- Improved retrieval with KG exact hits, vector fallback, role-aware retrieval, example completeness handling, and Chroma degradation.
- Added desktop packaging, first-run resource guidance, local asset status/download APIs, sample-data preparation, and data-safety tooling.
- Added chapter highlight generation, HTML artifacts, highlight reading page, chapter/section navigation, image support, LaTeX validation, and job-backed generation.
- Added project-level `AGENTS.md` conventions and moved durable architecture guidance out of patch notes.

### Validation

- Multiple historical runs of backend pytest and frontend production builds passed during those changes.
- Exact old command outputs are not reconstructed here because the source entries were encoding-damaged.
