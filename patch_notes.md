## 2026-07-10 - CPU-only desktop installer with three-book sample data

- Audited the desktop release changes after the previous CUDA DLL packaging failure.
- Confirmed the release dependency set pins torch 2.11.0+cpu and the GitHub desktop workflow installs requirements-release.txt.
- Found two remaining verification gaps: torch.cuda.is_available() can be false for a CUDA build without a working driver, and the old post-build check allowed a complete CUDA DLL set to pass.
- Hardened scripts/build-desktop-backend.ps1 to require an explicit +cpu torch version, require torch.version.cuda to be null, validate required sample data, and fail on any CUDA binary or PE import.
- Added scripts/verify_cpu_only_build.py, which parses Windows PE import tables without third-party dependencies and checks every packaged EXE/DLL, including shm.dll.
- Bundled desktop/sample_data_three_books as the seed dataset: 6435 files / 689.6 MiB, including the PDFs, OCR imports, progress/KG data, CPU embedding model, and clean Chroma index for 传感器短书、传感器长书、误差理论与数据处理. 优化设计 remains excluded.
- Rebuilt the PyInstaller backend and generated release/kaoyan-assistant-desktop-setup-0.1.0.exe.

### Validation

- Build environment: torch 2.11.0+cpu, torch.version.cuda=null, torch.cuda.is_available()=False.
- Fresh backend build passed the PE verification: 67 EXE/DLL files inspected, zero CUDA/NVIDIA binary names, and zero CUDA import references.
- Packaged shm.dll imports torch_cpu.dll and c10.dll; it does not reference torch_cuda.dll.
- Packaged seed contains 6435 files. All three PDF hashes match the source seed, and vector_db/chroma.sqlite3 also matches.
- Installer size: 564147970 bytes (538.0 MiB).
- Installer SHA-256: 57BFE1C17C539968BB24A5701B2F2AF9E258EE8D71032D5BD6338024C9ABE9E7.
- Frontend production build, PyInstaller backend build, and electron-builder NSIS build passed.
- A packaged-process /health smoke launch was attempted but blocked by the Codex execution-approval quota; this was not counted as passed.

---
## 2026-07-10 - High-priority reliability and local data safety fixes

- Moved streaming feedback persistence off the user-visible completion path. Streaming and non-streaming answers now survive learning-memory write failures; the SSE done event is no longer replaced by an error.
- Split local KG concept linking from background learning records and removed the automatic post-answer LLM concept-extraction fallback, preventing a hidden second LLM call before completion.
- Replaced automatic deletion of non-empty SQLite WAL/SHM/journal files with conservative recovery that removes only zero-byte artifacts and preserves files that may contain recoverable transactions.
- Added a URL scheme allowlist and a restrictive Content Security Policy to generated chapter-highlight HTML; executable, data, file, and protocol-relative links are no longer rendered as anchors.
- Lifted active chat cancellation into ChatContext, added AbortSignal support for non-streaming chat, and guarded stream callbacks by request generation so new/loaded conversations cannot be overwritten by stale events.
- Added striped per-conversation locks around JSON read-modify-write persistence to prevent concurrent message loss.
- Added regression coverage for stream completion, no automatic feedback LLM call, concurrent conversation writes, conservative SQLite recovery, and chapter-highlight HTML safety.

### Validation

- Full backend test suite passed: 71 passed, 3 warnings.
- Targeted high-priority regression suite passed: 12 passed, 3 warnings.
- Frontend tests passed: 2 test files, 7 tests.
- Frontend production build passed.
- Frontend lint completed with no errors and the existing HighlightRepositoryDialog.tsx hooks dependency warning.

---
## 2026-07-03 - RAG retrieval hardening and Chroma recovery

- Preserved final prompt chunk metadata in retrieval state via `retrieval_debug_items`, including rank, chapter, chunk id, source, role, section title, page index, direct-hit flag, TOC-like flag, and preview text.
- Changed the RAG evaluator to score the final prompt chunks instead of an intermediate KG-only order, and added `bootstrap` support for expanding KG-derived golden sets.
- Improved KG concept ranking so exact short concept names win over longer partial matches, while TOC/directory chunks are filtered or downranked before prompt assembly.
- Added section title and page index metadata to newly built vector chunks.
- Added `scripts/rebuild_vector_store_from_mineru.py` to safely rebuild Chroma from MinerU middle chunks with timestamped backups.
- Rebuilt the optimization-design vector store from MinerU output. Previous vector DBs were kept at `data/vector_db.backup-20260703-221607` and `data/vector_db.backup-20260703-222412`.
- Kept third-layer generated-answer evaluation opt-in; the external API retry was not used because it would send local textbook context outside the machine without explicit authorization.

### Validation

- `./venv310/Scripts/python.exe -B -m pytest tests/test_rag_retrieval_eval.py tests/test_rag_degradation.py tests/test_chat_stream_reliability.py -q` passed: `8 passed, 3 warnings`.
- `./venv310/Scripts/python.exe -B scripts/evaluate_rag.py run --golden data/eval/rag_golden_optimization_40.jsonl --output data/eval/rag_eval_report_40_top_level.json` completed outside the Windows sandbox so Chroma/SQLite journal writes could run normally.
- `./venv310/Scripts/python.exe -B scripts/evaluate_rag_ir_measures.py --report data/eval/rag_eval_report_40_top_level.json --output data/eval/rag_eval_ir_measures_report.json` passed using the external `ir_measures` library.
- Final 40-sample report: retrieval status `ok=40`, Hit@1 `0.775`, Hit@3 `0.975`, Hit@5 `1.0`, MRR `0.8729166667`, expected chapter hit rate `1.0`.
- External `ir_measures` cross-check matched the retrieval metrics and added ranking quality scores: `R@1=0.775`, `R@3=0.975`, `R@5=1.0`, `R@10=1.0`, `RR@10=0.8729166667`, `nDCG@3=0.8946394630`, `nDCG@5=0.9054063770`, `nDCG@10=0.9054063770`.
- Non-escalated SQLite probes still fail in the restricted Windows sandbox with `disk I/O error`; escalated local probes and the rebuilt Chroma evaluation succeed, indicating the observed failure is sandbox/journal related rather than a remaining retrieval-node crash.

---

## 2026-07-03 - Local RAG evaluation harness

- Added `scripts/evaluate_rag.py` for three-layer RAG checks: deterministic retrieval metrics, context relevance proxies, and optional generated-answer quality proxies.
- Added a starter JSONL golden set at `data/eval/rag_golden_optimization.jsonl` for the current optimization-design textbook index.
- Kept external evaluator libraries out of runtime dependencies; generated-answer checks are opt-in with `--with-generation` so retrieval experiments can run without API/network access.

### Validation

- `./venv310/Scripts/python.exe -B scripts/evaluate_rag.py --help` passed.
- `./venv310/Scripts/python.exe -B scripts/evaluate_rag.py run --limit 6 --output data/eval/rag_eval_report.json` completed; vector retrieval degraded because Chroma returned SQLite `disk I/O error`.
- `./venv310/Scripts/python.exe -B scripts/evaluate_rag.py run --limit 1 --with-generation --output data/eval/rag_eval_report_generation_sample.json` was attempted without escalation and recorded `Connection error`; escalated external API retry was rejected because it would send local textbook context to an external LLM.

---

# 2026-07-03

- Refined the Electron-only startup and window chrome polish: `desktop/loading.html` now uses the current black/white/blue Apple-inspired visual language with a frosted-glass panel, subtle entrance motion, reduced-motion fallback, and readable Chinese startup/error copy.
- Changed the Electron title controls from a full-width top strip into a floating glass control capsule with a narrow invisible drag strip, so the desktop app no longer looks like a browser page wrapped by a separate title bar.
- Kept the glass/motion treatment scoped to Electron startup/chrome as a low-risk trial before applying similar transitions to broader web/Electron modal surfaces.
- Added frontend typography tokens and mapped the Electron desktop chat shell, sidebar, home cards, toolbar, and composer to a smaller unified type scale.

### Validation

- `./venv310/Scripts/python.exe -B scripts/check_encoding.py --json encoding_audit_report.json --fail-on-issues` passed: `invalid_utf8=0`, `bom_files=0`, `suspicious_files=0`.
- `npm.cmd run build` passed.
- `npm.cmd run lint` completed with no errors and the existing `HighlightRepositoryDialog.tsx` React hooks dependency warning.

---
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

## 2026-07-04 OCR 教材向量索引导入

- 新增 `scripts/import_ocr_chunks.py`，用于将租卡 OCR 产物 `data/imports/kaoyan_ocr_20260704/deliverables/*_chunks.jsonl` 导入 Chroma。
- 已导入三本教材：`传感器短书` 562 chunks、`传感器长书` 943 chunks、`误差理论与数据处理` 511 chunks。
- `传感器短书` 与 `误差理论与数据处理` 标记为 `core`，`传感器长书` 标记为 `reference`，metadata 保留 `subject`、`book_role`、`rag_priority`、`review_status`、`source_markdown`。
- 因 `D:\AI\agent\kaoyan-assistant` 所在目录的 Windows 压缩/SQLite I/O 问题，Chroma 最终写入 `C:\tmp\chroma_smoke_test`，并在 `.env` 中设置 `VECTOR_DB_PATH=C:\tmp\chroma_smoke_test`。
- 验证：`get_vector_store()` 可加载 1589 个 collection；检索 `霍尔效应是什么` 能命中 `传感器短书` 中的定义 chunk。

## 2026-07-04 OCR 检索聚合索引优化

- 为三本 OCR 教材新增按书聚合 Chroma collection：`传感器短书`、`传感器长书`、`误差理论与数据处理` 各 1 个 aggregate collection，同时保留原有章节级 collection 供精确章节检索使用。
- `ChapterVectorStore.search_all()` 优先使用 book aggregate collection；无聚合索引时回退到旧的逐章节扫描。
- 启动预加载从全部章节 collection 改为只预加载 aggregate collection，避免 1500+ collection 冷启动开销。
- 最终 rerank 透传并使用 `book_role` / `rag_priority` metadata，使 `core` 教材优先于 `reference` 补充材料。
- 验证：`霍尔效应是什么` 在 `传感器短书` 内检索从约 40s 降至约 0.6s；跨书检索 `不确定度怎么合成` 扫描 3 个 aggregate collection，约 1.1s 返回 `误差理论与数据处理` 相关章节。


## 2026-07-04 OCR 教材 LLM 概念抽取与长书挂接

- 新增 scripts/extract_kg_candidates.py，支持对 OCR chunk 增量调用 DeepSeek V4 Pro 抽取 KG 候选，并过滤 thinking 内容，只落结构化 JSONL。
- 已对 传感器短书 与 误差理论与数据处理 的高价值语义块（definition/formula/theorem/derivation/example/exercise）完成主干概念抽取。
- 已按 传感器短书 高置信概念，将 传感器长书 高价值语义块挂接为 same_concept、expansion、proof、condition、edge_case、example_more、background 等关系。
- 产物位于 data/imports/kaoyan_ocr_20260704/deliverables/：kg_candidates_sensor_core.jsonl、kg_candidates_error_theory.jsonl、concept_links_sensor.jsonl、kg_review_queue.jsonl。
- 验证：传感器短书 165 chunk rows / 292 concepts；误差理论与数据处理 181 chunk rows / 228 concepts；传感器长书 364 links、32 no-match rows；低置信 review queue 49 rows。
## 2026-07-04 教材内习题抽取导入

- 新增教材抽题入口：`/api/exercises/textbook-analyze`，从已导入教材中按章节或页码范围提取候选题，并复用现有规则切题、低置信 LLM 修复和人工确认导入流程。
- 新增 `memory/textbook_exercise_importer.py`，抽取顺序为 chapter highlight `source_package.json`、MinerU `*_middle_chunks.json`、PDF 文本层；不修改现有教材索引、Chroma 向量库或题库结构。
- 前端习题库新增“从当前教材抽题”面板，支持章节/页码范围、习题页优先/章节例题/整页文本三种模式，候选题继续由用户勾选确认后入库。
- 验证：`python -m pytest tests/test_textbook_exercise_importer.py tests/test_exercise_importer.py -q` 通过；`npm run build` 通过；本地“优化设计”教材 page 50 可从 source_package 抽出候选题。

补充验证：已按 Electron 桌面端路径执行构建。`scripts/build-desktop-backend.ps1` 生成 `build/backend/backend_server/backend_server.exe`；`desktop/npm run dist` 生成 `release/win-unpacked` 与 `release/kaoyan-assistant-desktop-setup-0.1.0.exe`，内置 `frontend/dist` 时间戳已更新。

## 2026-07-04 教材问答概念与 OCR 抽题修复

- 修复流式问答 `done` 事件在 `feedback_node` 后台执行前就返回的问题，现在会把本轮 `linked_concepts` 同步写回 SSE state，避免非《优化设计》教材问答阶段前端拿不到概念链接。
- 教材抽题新增外部 OCR JSONL 读取路径，支持 `data/imports/.../*_chunks.jsonl` 产物；未找到 MinerU `middle_chunks` 时不再直接退化为“未提取到可切分文本”。
- Books API 对 `external_ocr_jsonl` 导入产生的“chunk 标题目录”做运行时目录折叠，从内嵌目录文本解析真实章节/小节，不改写现有 `_chapters.json` 数据文件。
- 前端习题库的教材抽题面板新增源 PDF/origin.pdf 预览入口，用户可先查看教材页，再输入起止页执行抽题。`r`n- 源 PDF 查找新增 `D:\OCR_NEEDED` 别名：`传感器短书 -> CGQ_1.pdf`、`传感器长书 -> CGQ_2.pdf`、`误差理论与数据处理 -> WC.pdf`，不复制原件。

### Validation

- `python -B -c "compile(...)"` 解析检查通过：`graph/main_graph.py`、`memory/textbook_exercise_importer.py`、`backend/api/books.py`。
- OCR 教材目录加载已折叠：`传感器短书` 13 章、`传感器长书` 12 章、`误差理论与数据处理` 7 章；外部 OCR 抽题路径返回 `external-ocr-jsonl` 文本。
- `npm.cmd run build` 通过。

## 2026-07-05 三本教材目录与桌面安装包打包

- 将 `Chapter.md` 中 Kimi 识别的目录写入三本教材：`传感器短书` 13 章、`传感器长书` 12 章、`误差理论与数据处理` 7 章；覆盖前保留 `_chapters.bak_chapter_md_*` 备份。
- 将 `D:\OCR_NEEDED\CGQ_1.pdf`、`CGQ_2.pdf`、`WC.pdf` 复制为 `data/books/传感器短书.pdf`、`传感器长书.pdf`、`误差理论与数据处理.pdf`，供桌面端 PDF 预览和 seed 数据使用。
- 新增错题/习题详情页删除入口，复用已有后端 DELETE API；删除后同步刷新列表、复习队列和统计状态。
- 构建了仅包含三本新教材的干净 Chroma 向量库与 `desktop/sample_data_three_books` seed 数据，不包含 `优化设计`。
- `scripts/build-desktop-backend.ps1` 增加 `-SampleDataDir` 参数，允许桌面后端构建显式指定 seed 数据目录。
- PyInstaller 输出中移除了本应用 CPU embedding 不需要的 CUDA/cuDNN DLL，使 NSIS 安装包避开 2GB mmap 限制；最终生成 `release/kaoyan-assistant-desktop-setup-0.1.0.exe`。

验证：

- `npm run build`：通过。
- `python -B` 编译检查 `backend/api/books.py`、`memory/textbook_exercise_importer.py`、`graph/main_graph.py`、`ingestion/pdf_parser.py`：通过。
- `scripts/build-desktop-backend.ps1 -SkipSampleDataPrepare -SampleDataDir desktop\sample_data_three_books`：通过。
- `npm run dist`：通过，生成 NSIS 安装包。
- release 内置 `sample_data` 抽查：6435 个文件，含三本 PDF，不含 `优化设计` 路径。
## 2026-07-11 教材 RAG 准确率 P0-P3 改造

### 原因与数据修复

- 定位“电容式传感器是否适合动态测量”只回答“质量轻”的根因：运行环境曾指向 `C:\tmp\chroma_smoke_test`，正式 `data/vector_db` 中没有《传感器长书》索引，模型实际依赖自身知识作答。
- 将运行时 `VECTOR_DB_PATH` 恢复为项目约定的 `./data/vector_db`；旧烟雾测试库保留，不执行删除。
- 为《传感器长书》在正式库中重建 12 个章节 collection、1359 个结构化 chunk；Dense 与 BM25 索引数量一致，健康检查通过。
- 本地 `torchvision` 与 `torch` 二进制不匹配会阻断 `sentence-transformers`。文本 Embedding 加载阶段现会隔离不需要的可选 `torchvision` 探测，不卸载或重装依赖。

### P0：索引完整性与安全降级

- 本地 PDF 导入现在也会构建教材索引，不再只解析章节而返回 `indexed_chunks=0`。
- 新增每本教材的 `collection_count`、`chunk_count`、`lexical_chunk_count`、`healthy` 健康统计，并在 Books API 列表中返回。
- 新增 `POST /api/books/{book_name}/reindex`，只重建派生检索资产，保留 PDF、OCR 原文、错题和学习记录。
- 教材存在但索引为空时返回 `book_index_empty`；教材模式无直接证据时强制拒答，不再静默使用模型参数知识补齐。

### P1：背诵准确模式与混合检索

- 新增 `factual_recall` 意图，用于原因、特点、优缺点、条件和并列要点等专业课背诵问题。
- 新增持久化本地 BM25 索引，采用 Dense Top 20 + BM25 Top 20 + RRF 融合；取消“第一个 role 有结果就停止”的硬过滤，role 改为软加权。
- 原 `_merge_and_rerank()` 的固定优先级排序改为问题相关的融合评分，保留 Dense/BM25/KG 来源、覆盖率和最终分数调试信息。
- 新增可选本地 Cross-Encoder 接口；设置 `RERANKER_MODEL_PATH` 后启用，未配置时使用确定性融合精排。
- 生成提示要求每个事实结论由选定教材证据支持；列表题必须穷尽证据中的并列项并附章节、小节、页码和 chunk_id。教材生成温度降为 0.1。
- 对年份、公式编号、英文缩写和数字参数增加精确字面证据约束，避免只有主题相似的段落冒充直接证据。

### P2：结构化切块与上下文补全

- 默认切块由 2000/100 字符调整为 700/80 字符，并优先按 Markdown 标题和自然段边界切分。
- chunk 新增 `section_path`、`parent_id`、`prev_chunk_id`、`next_chunk_id`、`parent_content` 和仅供检索使用的教材/章节前缀。
- Chroma 同时保存带上下文的 `retrieval_text` 与不带前缀的 `raw_content`；生成阶段使用原始教材正文。
- BM25 命中后支持相邻块扩展；公式、例题和列表可沿文档顺序补足上下文。

### P3：评测与回归

- 新增 `evaluation/rag_eval.py`，支持离线计算 Recall@K、MRR、要点完整率以及不可回答题拒答结果。
- 新增 `evaluation/datasets/textbook_recall.jsonl` 首批专业课背诵评测集，以及事实意图、RRF、切块关系、要点完整率和空索引拒答测试。
- 关键回归“电容式传感器是否适合动态测量”在正式库中排名 Top 1，Dense 与 BM25 双命中，同一证据完整包含“静电引力很小、质量很轻、介质损耗小”。
- 当前 10 题离线基线：Recall@10 为 80%，要点召回率为 83.3%；剩余薄弱项主要是完整特点块的标题排序和跨连续小节的列表聚合，作为后续调参基线保留。

### Validation

- `.\venv310\Scripts\python.exe -B -m pytest -q`：77 passed，3 warnings。
- `frontend/npm.cmd run build`：通过，Vite production build 成功。
- 正式《传感器长书》索引健康统计：12 collections / 1359 vector chunks / 1359 lexical chunks。
- 关键案例 Top 1 chunk：`3e87d09788d31566`，章节“第4章 力敏传感器”，融合来源 `dense + bm25`。

## 2026-07-11 传感器问答检索与展示修复

- 从保留的 OCR chunks 重建传感器短书索引：479 个章节 collection、562 个 chunk，并补建 562 条 BM25 索引；未改动长书索引、OCR 源和学习记录。
- 传感器问答改为分层联邦检索：短书为 core 主证据，长书作为 reference 补证；两库保持独立以保留来源追踪。
- 生成提示与前端双重隐藏内部 chunk ID；Markdown 不再保留源文本缩进空白，并折叠过量空行。
- 追问改写不再把所有短问题一律视为追问，只对显式指代词启用上下文；历史输入会清除内部索引号。
- 重建脚本复用项目文本嵌入加载器，规避不兼容 torchvision，并支持 KAOYAN_IMPORT_BOOKS 选择性重建。

验证：Python 语法检查通过；frontend npm run build 通过；短书 Chroma 与 BM25 计数见上。


## 2026-07-11 - P0/P1 evaluation, latency trace, and runtime convergence

- Extended the gold-set evaluator with expected chunk recall/MRR, forbidden-chunk detection, expected-page hits, and per-query retrieval latency.
- Added bounded SQLite RAG traces (last 500 requests) with request ID, fast-path flag, TTFT, total time, stage timings, and evidence metadata; answer text and model thinking are not stored.
- Added `GET /api/system/rag-traces`, trace database health, and LLM runtime-configuration health.
- Added request IDs and elapsed milliseconds to chat SSE events and replaced backend startup/chat `print` diagnostics with structured logging.
- Retired the obsolete Gradio web entry and removed Gradio from the development dependency list. Electron + React + FastAPI remains the supported product path; the root CLI is explicitly legacy.

### Validation

- `python -B -m pytest -q`: 79 passed, 1 dependency deprecation warning.
- `frontend/npm.cmd run build`: passed (TypeScript and Vite production build).
- `git diff --check`: passed.
