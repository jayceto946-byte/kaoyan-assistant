# Patch Notes 鈥?鑰冪爺鏅鸿兘杈呭姪绯荤粺

---
## v0.7.12 - 2026-06-24
### P0: core workflow stability, light-theme readability, and diagnostics
- **Added** `backend/api/system.py` and `/api/system/health`.
  - Report vector store, knowledge graph, mistake book, and exercise bank as `healthy`, `degraded`, or `error`.
  - Use read-only SQLite integrity checks so diagnostics do not create or mutate user databases.
- **Added** `frontend/src/components/SystemHealth.tsx`.
  - Show a compact sidebar status with expandable component details, manual refresh, 30-second polling, and stale-request protection when switching books.
- **Changed** light-theme status styles across books, exercises, mistakes, concept popovers, and render errors.
  - Replace unreadable dark-theme blue/green/red/amber text with warm-theme success, warning, danger, and accent colors.
- **Operational**
  - Recovered a stale `chroma.sqlite3-journal` through SQLite integrity recovery without deleting the vector database.
  - Removed empty SQLite files and a DOCX artifact created by this validation run.

### Validation
- Full test suite: `30 passed, 1 skipped`.
- Frontend production build passes; the existing large-chunk warning remains.
- Browser smoke test passes for chat shell, textbook switching and two-level TOC, mistake capture page, exercise import page, learning review page, book import, and knowledge graph.
- Live system health reports 313 vector collections, 871 knowledge graph concepts, and healthy mistake/exercise databases for the selected textbook.

---
## v0.7.11 - 2026-06-23
### Fix: Chroma disk I/O recovery and retrieval fallback
- **Changed** `ingestion/vector_store.py`
  - Add a vector-store availability flag so Chroma/SQLite open failures degrade retrieval to empty results instead of crashing chat.
  - Guard collection listing and full-library search against Chroma `disk I/O error`.
- **Operational**
  - Stopped the stale backend process, let SQLite recover the leftover `chroma.sqlite3-journal`, removed temporary vector DB probe files, and restarted the backend on port 8000.

### Validation
- Non-sandbox SQLite `pragma integrity_check` returns `ok`.
- Non-sandbox Chroma opens `data/vector_db` and lists 313 collections.
- Chat pipeline reaches `retrieve` with `content_count=1` for `鍑芥暟鏄粈涔坄 without disk I/O errors.

---
## v0.7.10 - 2026-06-23
### UI: expandable chapter tree and bordered controls
- **Changed** `backend/api/books.py`
  - Return chapter `end_page` and nested `subsections` from book current/switch APIs.
- **Changed** `frontend/src/components/ChapterTree.tsx`
  - Replace the flat chapter list with an expandable two-level chapter/section tree, including page ranges and section pages.
- **Changed** `frontend/src/layouts/MainLayout.tsx` and `frontend/src/index.css`
  - Put 褰撳墠鏁欐潗 and 鐩綍 into bordered workspace panels.
  - Add a reusable bordered `app-select` style and remove the raw browser-like select appearance.

### Validation
- `npm.cmd run build` passes; Vite still reports the existing large chunk warning.
- Live API returns `subsections`, and browser smoke check confirms the sidebar renders expandable second-level sections.

---
## v0.7.9 - 2026-06-23
### UI: Claude-inspired study workspace theme
- **Changed** `frontend/src/index.css`
  - Replace the dark blue theme with a warm paper palette, clay accent color, low-contrast borders, and light scrollbar/input defaults.
- **Changed** `frontend/src/layouts/MainLayout.tsx`
  - Restyle the app shell as a warm study workspace with paper-like sidebar, restrained navigation states, and clearer Chinese labels.
- **Changed** `frontend/src/pages/ChatPage.tsx` and `frontend/src/components/ChatMessage.tsx`
  - Restyle the chat surface, empty state, composer, markdown code blocks, concept chips, and assistant/user bubbles for the light workspace theme.

### Validation
- `npm.cmd run build` passes; Vite still reports the existing large chunk warning.
- Browser smoke check on `http://127.0.0.1:5173` confirms the chat and exercise pages render with the new warm theme.

---
## v0.7.8 - 2026-06-23
### Feature: book/subject-scoped exercise import
- **Changed** `frontend/src/pages/ExercisesPage.tsx`
  - Add an import target selector for existing books plus manual subject/book naming.
  - Use the selected target as both the exercise bank `book_name` namespace and default `subject`, so imported exercises can align with later textbook imports.
  - Keep OCR out of the default flow; scanned PDFs remain flagged by text extraction warnings.

### Validation
- `python -m pytest tests/test_exercise_file_importer.py tests/test_exercise_importer.py tests/test_exercise_bank.py -q` passes: 7 passed.
- `npm.cmd run build` passes; Vite still reports the existing large chunk warning.

---
## v0.7.7 - 2026-06-23
### Feature: direct Word/PDF exercise import
- **Added** `memory/exercise_file_importer.py`
  - Extract text from `.docx` using standard-library ZIP/XML parsing.
  - Extract text-layer PDF content with PyMuPDF and report pages that need OCR.
- **Changed** `backend/api/exercises.py`
  - Add `/api/exercises/upload-analyze` to save uploaded Word/PDF files under local data uploads, extract text, split candidates, and run low-cost rule analysis.
- **Changed** `frontend/src/pages/ExercisesPage.tsx`
  - Add direct Word/PDF selection and file analysis in the exercise import panel, while keeping pasted-text analysis as a fallback.
- **Added** `tests/test_exercise_file_importer.py`
  - Cover DOCX extraction, PDF text extraction, and upload-to-candidate analysis.

### Validation
- `python -m pytest tests/test_exercise_file_importer.py tests/test_exercise_importer.py tests/test_exercise_bank.py -q` passes: 7 passed.
- `npm.cmd run build` passes; Vite still reports the existing large chunk warning.

---
## v0.7.6 - 2026-06-23
### Feature: low-cost exercise import triage
- **Added** `memory/exercise_importer.py`
  - Add rule-based candidate splitting and low-cost exercise analysis without default LLM calls.
  - Detect likely question type, difficulty, concept tags, linked concept candidates, confidence, and whether a candidate should be sent to later LLM refinement.
- **Changed** `backend/schemas.py` and `backend/api/exercises.py`
  - Add `/api/exercises/analyze-candidates` for fast draft analysis.
  - Add `/api/exercises/batch-add` for confirmed candidate import.
- **Changed** `frontend/src/pages/ExercisesPage.tsx` and `frontend/src/types/index.ts`
  - Add a batch import draft panel: paste parsed Word/PDF text, analyze candidates, review confidence, select candidates, and batch import into the exercise bank.
- **Added** `tests/test_exercise_importer.py`
  - Cover candidate splitting, heuristic labels, API analysis, and batch import.

### Validation
- `python -m pytest tests/test_exercise_bank.py tests/test_exercise_importer.py -q` passes: 4 passed.
- `npm.cmd run build` passes; Vite still reports the existing large chunk warning.

---
## v0.7.5 - 2026-06-23
### Fix: exercise bank route stability
- **Changed** `backend/api/exercises.py`
  - Move static POST routes (`/status`, `/from-mistake`) before dynamic `/{exercise_id}` routes to keep exercise bank endpoints robust.
  - Verified `POST /api/exercises/list?book_name=浼樺寲璁捐` returns 200 from the current app route table.

### Note
- If the browser still reports 405 after this patch, restart the running FastAPI backend; the active server is likely using an older route table.

---
## v0.7.4 - 2026-06-23
### Feature: 涔犻搴撴渶灏忛棴鐜?

- **Added** `memory/exercise_bank.py`
  - Add SQLite-backed `ExerciseRecord` / `ExerciseBank` as a general question asset layer.
  - Fields are compatible with mistake records: question, answer, explanation, source, subject, chapter, tags, type, difficulty, image/OCR, linked concepts, origin, status, and notes.
- **Changed** `backend/schemas.py`
  - Add exercise request/response schemas.
- **Added** `backend/api/exercises.py`
  - Add exercise CRUD/list/stats/status endpoints.
  - Add `/api/exercises/from-mistake` to copy a mistake into the exercise bank while preserving `origin_type="mistake"` and `origin_id`.
- **Changed** `backend/main.py`
  - Register the exercises router.
- **Added** `frontend/src/pages/ExercisesPage.tsx`
  - Add a usable exercise bank page with manual entry, filtering, stats, expandable details, Markdown/LaTeX rendering, and status updates.
- **Changed** `frontend/src/App.tsx`, `frontend/src/layouts/MainLayout.tsx`, and `frontend/src/types/index.ts`
  - Add route, sidebar navigation, and exercise TypeScript types.
- **Added** `tests/test_exercise_bank.py`
  - Cover storage CRUD/stats and API add/list/status/from-mistake flow.

### Validation

- `python -m pytest -q` passes: 23 passed, 1 skipped.
- `npm.cmd run build` passes; Vite still reports the existing large chunk warning.

---
## v0.7.3 - 2026-06-23
### P2: 瀛︿範璁板繂浜у搧鍖栫涓€姝?

- **Changed** `knowledge/concept_memory.py`
  - Add `mark_reviewed()` to record explicit concept review events, review count, last review time, review quality, and weak/mastery updates.
- **Changed** `backend/api/kg.py`
  - Extend `/api/kg/learning-summary` with `concept_review_plan`, an actionable concept review card list.
  - Review cards include priority, reasons, recent questions, related mistakes, and textbook/KG snippets.
  - Add `/api/kg/concept-review` to record that a concept has been reviewed from the Learning page.
- **Changed** `frontend/src/pages/LearningPage.tsx`
  - Add a 鈥滀粖鏃ユ蹇靛涔犫€?section above existing learning stats.
  - Each concept card shows review reasons, textbook cues, related mistakes, recent questions, and an 鈥滃凡澶嶄範鈥?action.
- **Added** `tests/test_learning_memory_api.py`
  - Covers concept review plan generation and explicit concept review recording with isolated local data.

### Validation

- `python -m pytest -q` passes: 21 passed, 1 skipped.
- `npm.cmd run build` passes; Vite still reports the existing large chunk warning.

---
## v0.7.2 - 2026-06-23
### Security: remove hardcoded API keys and expand local ignores

- **Changed** `knowledge/kg_phase1.py` and `knowledge/kg_phase6.py`
  - Remove hardcoded DeepSeek API keys.
  - Load `DEEPSEEK_API_KEY`, `DEEPSEEK_API_BASE`, and `DEEPSEEK_KG_MODEL` / `DEEPSEEK_MODEL_NAME` from `.env` / environment variables.
  - Raise a clear runtime error if `DEEPSEEK_API_KEY` is missing before running these standalone KG scripts.
- **Changed** `.gitignore`
  - Add local secrets, API text files, key/pem files, SQLite/DB backups, assistant logs, OCR/TOC samples, local data, generated indexes, virtualenvs, frontend artifacts, and diagnostic scratch files.

### Validation

- `ast.parse` passes for `knowledge/kg_phase1.py` and `knowledge/kg_phase6.py`.
- Source scan excluding ignored local/private directories finds no remaining `sk-...` style hardcoded key in uploadable code.

---
## v0.7.1 - 2026-06-23
### P0: 鏁版嵁瀹夊叏涓庢湰鍦?smoke 鍩虹嚎

- **Changed** `.gitignore`
  - 鎵╁睍蹇界暐瑙勫垯锛屾帓闄ゅ墠绔瀯寤轰骇鐗┿€佷緷璧栫洰褰曘€佹湰鍦板涔犳暟鎹€佸悜閲忓簱銆丮inerU 杈撳嚭銆佸浠藉寘涓庝复鏃惰瘖鏂枃浠躲€?
- **Added** `docs/data_safety.md`
  - 鏄庣‘ `data/progress`銆乣data/images`銆乣data/books`銆乣data/chapters`銆乣data/vector_db`銆乣mineru_output` 鐨勬暟鎹畨鍏ㄨ竟鐣屻€?
  - 璁板綍楂橀闄╂搷浣滃墠鐨勫浠戒笌楠岃瘉娴佺▼銆?
- **Added** `scripts/backup_learning_data.ps1`
  - 鏂板鏈湴瀛︿範璧勪骇澶囦唤鑴氭湰锛岄粯璁ゆ墦鍖?`data/progress`銆乣data/images`銆乣data/books`銆乣data/chapters` 鍒?`backups/`銆?
- **Added** `tests/test_smoke_workflows.py`
  - 鏂板鏃?LLM銆佹棤缃戠粶鐨勬湰鍦?smoke 娴嬭瘯锛岃鐩?health銆侀敊棰樻柊澧炪€佸垪琛ㄣ€佷粖鏃ュ涔犮€佸涔犺褰曘€佺粺璁″拰钖勫急鐐广€?

### P1: 閿欓澶嶄範闂幆鍙嶉

- **Changed** `backend/api/mistakes.py`
  - `/api/mistakes/review` 杩斿洖鏇存柊鍚庣殑閿欓璁板綍銆乣next_review` 鍜?`interval`锛屾柟渚垮墠绔嵆鏃跺睍绀哄涔犵粨鏋溿€?
- **Changed** `frontend/src/pages/MistakesPage.tsx`
  - 浠婃棩澶嶄範璇勫垎鍚庡嵆鏃舵洿鏂版湰鍦拌褰曪紝骞舵樉绀衡€滃凡璁板綍澶嶄範锛孨 澶╁悗鍐嶇湅鈥濈殑鍙嶉銆?
- **Changed** `memory/mistake_book.py`
  - 钖勫急鐐逛腑鐢辨爣绛?姒傚康浜х敓鐨勬潯鐩被鍨嬫樉绀轰负鈥滅煡璇嗙偣鈥濄€?
- **Changed** `tests/test_mistake_book.py`
  - 琛ュ厖 SM-2 涓嬫澶嶄範鏃ユ湡鍜岃杽寮辩偣绫诲瀷鏂█銆?

### Validation

- `python -m pytest -q` passes: 20 passed, 1 skipped.
- `npm.cmd run build` passes; Vite still reports the existing large chunk warning.

---
## v0.7.0 - 2026-06-22
### Feature: 閿欓鏈湅鍥捐瘑棰樿В绛旈棴鐜?

- **Changed** `backend/api/mistakes.py`
  - 鏂板 `/api/mistakes/recognize-image`锛氫笂浼犻敊棰樺浘鐗囧悗淇濆瓨鍒?`data/images/mistakes`锛岃皟鐢?PaddleOCR 杩斿洖鍙紪杈?OCR 棰樺共涓庡浘鐗囪矾寰勩€?
  - 鏂板 `/api/mistakes/solve-image`锛氫笂浼犲浘鐗囧悗 OCR 骞剁洿鎺ョ敓鎴愯瑙ｏ紝杈撳嚭鍓嶇户缁繃婊?thinking 骞舵竻娲?LaTeX銆?
  - 鏂板 `/api/mistakes/solve-text`锛氬鐢ㄦ埛鏍″鍚庣殑棰樺共鐩存帴鐢熸垚璁茶В锛屼笉瑕佹眰鍏堜繚瀛樺埌閿欓鏈€?
  - 淇濆瓨閿欓鏃舵敮鎸?`image_path`锛屼娇鍥剧墖鏉ユ簮涓庨敊棰樿褰曞叧鑱斻€?
- **Changed** `backend/schemas.py`
  - `MistakeAddRequest` 澧炲姞 `image_path` 瀛楁銆?
- **Changed** `frontend/src/pages/MistakesPage.tsx`
  - 閲嶅仛閿欓鏈〉闈㈠綍鍏ュ伐浣滃彴锛氬浘鐗囬瑙堛€丱CR 璇嗗埆銆丱CR 鏂囨湰鏍″銆佺湅鍥捐В绛斻€佷繚瀛橀敊棰樺湪鍚屼竴娴佺▼鍐呭畬鎴愩€?
  - 鍒楄〃椤靛鍔犫€滆棰樷€濇寜閽紝澶嶇敤鍚庣閿欓璁茶В鎺ュ彛銆?
  - 淇濈暀浠婃棩澶嶄範銆佺粺璁′笌钖勫急鐐硅鍥撅紝骞朵慨澶嶅師椤甸潰澶氬涔辩爜鏂囨銆?
- **Validation**
  - `npm.cmd run build` passes.
  - `python ast.parse` passes for `backend/api/mistakes.py` and `backend/schemas.py`.
  - `import backend.api.mistakes` passes, confirming multipart upload route registration works in the current environment.

### Follow-up: Kimi Vision OCR + remove difficulty option

- **Changed** `backend/api/mistakes.py`
  - Switch mistake image OCR from local PaddleOCR to Kimi Vision (`KIMI_VISION_MODEL`, default `kimi-k2.5`).
  - Keep DeepSeek V4 Pro as the solving model: image -> Kimi OCR text -> DeepSeek explanation.
  - Add image downsampling before OCR: uploaded images are converted to an OCR working JPEG, longest side defaults to `1600px`, quality defaults to `86`.
- **Changed** `frontend/src/pages/MistakesPage.tsx`
  - Remove the difficulty selector and difficulty display from the mistake workflow.
- **Changed** `.env.example`
  - Add `KIMI_VISION_MODEL`, `MISTAKE_OCR_MAX_SIDE`, and `MISTAKE_OCR_JPEG_QUALITY` examples.
- **Validation**
  - `npm.cmd run build` passes.
  - `import backend.api.mistakes` passes.

---
## v0.6.9 - 2026-06-22
### Bug fix: long chat answer render fallback

- **Changed** `frontend/src/components/ChatMessage.tsx`
  - Render long assistant messages in smaller Markdown blocks to reduce parser/KaTeX pressure.
  - Add per-block fallback so one malformed Markdown/LaTeX fragment degrades to plain text instead of replacing the whole answer with an error card.
  - Protect inline math and existing links before concept-link injection, reducing formula corruption when concepts are highlighted.
- **Changed** `frontend/src/components/ErrorBoundary.tsx`
  - Add `resetKey` so transient streaming render errors can recover as content updates.
  - Fix the fallback text to render readable Chinese through unicode escapes.
- **Validation**
  - `npm.cmd run build` passes.

### Follow-up fix: visible unicode escapes and safer concept links

- **Changed** `frontend/src/components/ChatMessage.tsx`
  - Replace visible `\u...` JSX text with real UI strings, fixing the `\u601d\u8003\u4e2d...` loading text.
  - Tokenize newly inserted concept links so later alias matches cannot append duplicate `(#concept-...)` fragments.
  - Make long-message splitting more conservative: only split on blank lines while outside code fences and both block/inline math.
- **Changed** `frontend/src/components/ErrorBoundary.tsx`
  - Restore readable fallback copy.
- **Validation**
  - `npm.cmd run build` passes.
  - Local concept-link simulation confirms no duplicate concept href is appended.

### Follow-up fix: strict learning concepts and question-centric learning view

- **Changed** `knowledge/concept_memory.py` and `graph/feedback_node.py`
  - Persist and return only strict 100% confidence concepts for learning memory.
  - Require the concept name or a non-generic alias to appear in the user question, so generic aliases like iteration/step/method do not become memory concepts.
- **Changed** `backend/api/kg.py`
  - Filter historical learning summary data with the same strict rule.
  - Add `recent_questions`, grouping concepts under each question instead of repeating one question per concept.
- **Changed** `frontend/src/pages/LearningPage.tsx`
  - Render the Learning page as question-centric rows with concept chips under each question.
- **Validation**
  - Summary smoke test: simplex iteration keeps only simplex-table concept; unconstrained optimization keeps only unconstrained optimization concept.
  - `npm.cmd run build` passes.

---
## v0.6.8 鈥?2026-06-21
### 鏂囨。鏁寸悊锛欰GENTS.md 鍙繚鐣欑ǔ瀹氱害瀹?

- **璋冩暣** `AGENTS.md`
  - 绉婚櫎鐗堟湰琛ㄣ€佸巻鍙茶縼绉昏鏄庛€佸凡淇 bug 鍒楄〃銆佸甫鏃ユ湡鐨勫疄鐜拌褰曘€佺幆澧冨疄娴嬫祦姘磋处绛夌増鏈洿杩唴瀹广€?
  - 淇濈暀骞堕噸缁勪负锛氶」鐩洰鐨勩€佹牳蹇冨師鍒欍€佹妧鏈害鏉熴€佸綋鍓?FastAPI + React 鏋舵瀯銆佹牳蹇冨伐浣滄祦銆佸姛鑳藉彇鑸嶃€佹湭鏉ョ洰鏍囥€佸父鐢ㄥ懡浠ゃ€佹枃妗ｇ淮鎶よ鍒欍€?
  - 鏂板闀挎湡绾︽潫锛歋SE 浜嬩欢椤哄簭銆丷eact StrictMode 涓?updater 蹇呴』淇濇寔绾嚱鏁般€丆hroma 鍚戦噺搴撶洰褰曟潈闄?鍘嬬缉灞炴€ц姹傘€丄GENTS 涓?patch_notes 鐨勮亴璐ｈ竟鐣屻€?
- **褰掓。鍘熷垯**
  - 鍚庣画鐗堟湰鏇磋凯銆乥ug 淇銆佹灦鏋勮縼绉诲巻鍙层€佺幆澧冧慨澶嶈褰曠户缁啓鍏?`patch_notes.md`銆?
  - `AGENTS.md` 鍙湪闀挎湡绾︽潫銆佸綋鍓嶆灦鏋勬垨鏈潵鐩爣鍙戠敓鍙樺寲鏃舵洿鏂般€?
### 杩藉姞淇锛歊eact StrictMode 涓嬫祦寮?chunk 琚噸澶嶈拷鍔?

- **鏍瑰洜**锛歚frontend/src/hooks/useChat.ts` 鎶?`streamContentRef.current += event.chunk` 鏀惧湪 `updateLastMessage()` 鐨?React state updater 鍐呴儴銆俁eact 寮€鍙戞ā寮?StrictMode 浼氳皟鐢?updater 涓ゆ浠ユ鏌ョ函鍑芥暟锛屽鑷存瘡涓?SSE chunk 琚拷鍔犱袱閬嶏紝鍑虹幇鈥滄湰鏈暀鏉愭暀鏉愮粰鍑虹殑缁欏嚭鐨勨€濊繖绫婚噸澶嶆枃鏈€?
- **淇**锛氬皢 `streamContentRef` 鍜?`sourceChaptersRef` 鐨勫啓鍏ュ叏閮ㄧЩ鍒?`updateLastMessage()` 澶栭儴锛泆pdater 鍐呭彧璇诲彇宸茬粡璁＄畻濂界殑 `nextStreamContent` 骞惰繑鍥炴柊 message锛屼繚鎸佺函鍑芥暟銆?
- **楠岃瘉**锛氭ā鎷?updater 鍙岃皟鐢ㄦ椂鍚屼竴 chunk 鍙拷鍔犱竴娆★紱`npm run build` 閫氳繃銆?
### 杩藉姞淇锛氭祦寮忛暱鍐呭鐢熸垚鍚庤鈥滄暣鐞嗚瑙ｅ唴瀹光€濊鐩?

- **鏍瑰洜**锛歚graph/main_graph.py` 鐨?teach 娴佸紡璺緞鍏堝彂閫佸ぇ閲?`generate` chunk锛屾鏂囧凡缁忓湪鍓嶇绱瀹屾垚鍚庯紝鍙堝彂閫佷簡涓€娆?`stage=chapter` 浜嬩欢锛沗frontend/src/hooks/useChat.ts` 鏀跺埌 `chapter` 浼氭棤鏉′欢鎶?assistant 娑堟伅鍐呭鏇挎崲鎴?`馃摉 鏁寸悊璁茶В鍐呭鈥锛屽鑷撮暱杈撳嚭鍏ㄦ枃娑堝け銆?
- **淇** `graph/main_graph.py`
  - `stage=chapter` 鏀逛负鍦?teach 姝ｆ枃娴佸紡鐢熸垚鍓嶅彂閫?
  - 绉婚櫎姝ｆ枃鐢熸垚鍚庣殑杩熷埌 `chapter` 浜嬩欢锛屼繚璇佷簨浠堕『搴忎负 `plan -> retrieve -> chapter -> generate -> done`
- **淇** `frontend/src/hooks/useChat.ts`
  - 浣跨敤 `streamContentRef` 鐙珛绱Н娴佸紡姝ｆ枃锛屼笉鍐嶄緷璧栧綋鍓?React message content 浣滀负鍞竴绱姞婧?
  - 闃舵浜嬩欢鍦ㄦ秷鎭繘鍏?`generate/done` 鍚庝笉鍐嶈鐩栨鏂?
  - 鏀寔鍚庣 `stage=error` SSE 浜嬩欢锛岄伩鍏嶅紓甯歌闈欓粯蹇界暐
- **鍚屾** `frontend/src/api/client.ts` / `frontend/src/types/index.ts` 澧炲姞 SSE `message` / `error` 绫诲瀷銆?
- **楠岃瘉**锛氬娴嬧€滅粰鎴戣涓€涓嬪崟绾舰娉曡凯浠ｆ楠も€濅簨浠堕『搴忔纭紱`npm run build` 閫氳繃锛沗pytest -q` 閫氳繃銆?
### 杩藉姞淇锛氱珷鑺傛绱?Chroma HNSW 娈电己澶卞鑷?SSE 宕╂簝

- **淇** `ingestion/vector_store.py`
  - `search_chapter()` 鎹曡幏 Chroma 鍐呴儴閿欒锛堝 `Error creating hnsw segment reader: Nothing found on disk`锛夛紝绉婚櫎璇ョ珷鑺傜紦瀛樺苟杩斿洖绌虹粨鏋?
  - 涓婂眰鍙嚜鍔?fallback 鍒板叏搴撴绱紝閬垮厤鍗曚釜鎹熷潖 collection 鎵撴柇鏁存潯瀵硅瘽娴?
- **淇** `backend/api/chat.py`
  - SSE generator 澧炲姞澶栧眰寮傚父鍏滃簳锛屽悗绔紓甯歌浆涓?`stage=error` 浜嬩欢杩斿洖鍓嶇锛屼笉鍐嶅啋娉℃垚 ASGI `ExceptionGroup`
- **楠岃瘉**锛氬娴嬧€滅粰鎴戣涓€涓嬪崟绾舰娉曡凯浠ｆ楠も€濆彲杩涘叆娴佸紡鐢熸垚锛涙ā鎷熸崯鍧?collection 鏃?`search_chapter()` 杩斿洖绌哄垪琛ㄤ笖涓嶆姏鍑恒€?

### Code Review 淇锛氭瀯寤洪樆濉炪€佹绱㈠懡涓€佽矾鐢遍『搴忎笌闃诲娌荤悊

- **淇** `frontend/src/components/ErrorBoundary.tsx`
  - `ReactNode` 鏀逛负 type-only import锛屽吋瀹?`verbatimModuleSyntax`
  - 淇 fallback JSX 鏂囨闂悎閿欒锛屽墠绔敓浜ф瀯寤烘仮澶嶉€氳繃

- **淇** `knowledge/knowledge_graph.py`
  - `search_concept()` 鏀寔鈥滄蹇靛悕鍖呭惈鍦ㄧ敤鎴锋暣鍙ラ棶棰樹腑鈥濈殑鍙嶅悜鍛戒腑
  - 瑙ｅ喅鈥滀粈涔堟槸鍗曠函褰㈡硶鈥濇棤娉曡Е鍙?KG 绮剧‘妫€绱€侀€€鍖栧埌绾悜閲忔绱㈢殑闂
  - `graph` 鏃ф牸寮忚浆鎹㈠鍔犲疄渚嬬紦瀛橈紝閬垮厤 API/鍙鍖栭噸澶嶆瀯閫犲ぇ瀛楀吀

- **淇** `backend/api/mistakes.py`
  - `/stats`銆乣/weak-points` 闈欐€佽矾鐢辩Щ鍔ㄥ埌 `/{mistake_id}` 鍓嶏紝閬垮厤琚姩鎬佽矾鐢卞悶鎺?

- **浼樺寲** 鍚戦噺搴撳鐢?
  - `graph/planner.py`銆乣graph/chapter_subgraph.py`銆乣backend/api/mistakes.py`銆乣knowledge/kg_visualizer.py` 鏀圭敤 `get_vector_store()` 鍗曚緥
  - 閬垮厤姣忔璇锋眰閲嶅鍒濆鍖?`ChapterVectorStore()`銆侀噸澶嶉鍔犺浇 Chroma collection

- **浼樺寲** 绔犺妭璁茶В鍚庡彴浠诲姟
  - 妫€绱笉鍒扮珷鑺傚唴瀹规椂涓嶅啀鍚姩 keypoints/quiz 鍚庡彴 LLM 浠诲姟
  - 鍚庡彴浠诲姟缁撴灉鍙湪宸插畬鎴愭椂鏀堕泦锛涙湭瀹屾垚鍒欏彇娑堝苟璺宠繃锛岄伩鍏?`.result()` 闃诲涓诲洖绛?
  - executor 缁熶竴 `shutdown(wait=False, cancel_futures=True)`锛岄檷浣庣嚎绋嬫畫鐣欓闄?

- **淇** 娴嬭瘯鍏ュ彛
  - `test_chapters.py` 鏍囪涓烘墜鍔ㄧ储寮曡剼鏈紝pytest 鏀堕泦鏃惰烦杩囷紝閬垮厤 collection 闃舵鍐?Chroma
  - `utils/latex_sanitizer.py` 淇 invalid escape warning

#### 楠岃瘉

- `npm run build` 鉁?
- `python AST parse` 鉁?44 涓?Python 鏂囦欢鏃犺娉曢敊璇?
- `pytest -q` 鉁?13 passed, 1 skipped

---
## v0.6.7 鈥?2026-06-16

### Bug 淇锛欴eepSeek thinking 杈撳嚭杩囨护 + 渚嬮棰樺共鍙洖鐜?

#### Bug 1锛歀LM 杈撳嚭澶ч噺鎺ㄧ悊杩囩▼锛屾寮忓洖绛旇娣规病

**鏍瑰洜**锛歚config.py` 鍚敤浜?DeepSeek V4 Pro thinking 妯″紡锛坄reasoning_effort: high, thinking: enabled`锛夛紝妯″瀷浼氬湪 `<think>...</think>` 鏍囩鍐呰緭鍑哄唴閮ㄦ帹鐞嗛摼锛?璁╂垜鍏堝垎鏋愭绱㈠唴瀹?.."锛夛紝鐩存帴鏆撮湶缁欑敤鎴枫€?

**淇**锛氫繚鐣?thinking 妯″紡锛堣川閲忔彁鍗囨樉钁楋級锛屼絾**杩囨护杈撳嚭**銆?

- **鏂板** `utils/thinking_filter.py`
  - `ThinkingFilter`锛氭祦寮忚繃婊ゅ櫒锛屾敮鎸佽法 chunk 鐨?`<think>...</think>` 鏍囩锛堢姸鎬佹満瀹炵幇锛?
  - `strip_thinking()`锛氫竴娆℃€ц繃婊わ紝鐢ㄤ簬闈炴祦寮忓満鏅?

- **淇敼** `graph/main_graph.py` 鈥?娴佸紡瀵硅瘽涓昏矾寰?
  - teach 璺緞鍜?generate 璺緞鐨?`llm.stream()` 杈撳嚭鍧囩粡杩?`ThinkingFilter`
  - 娴佺粨鏉熻皟鐢?`flush()` 纭繚鏃犳畫鐣?

- **淇敼** `graph/generator.py` 鈥?闈炴祦寮忚矾寰?
  - `generate_node()` 鍦?`sanitize_latex()` 涔嬪墠鍏堣皟鐢?`strip_thinking()`

- **淇敼** `graph/chapter_subgraph.py` 鈥?鍚庡彴浠诲姟
  - `_extract_keypoints()` / `_generate_quiz()` 鍦?JSON 瑙ｆ瀽鍓嶅厛杩囨护 thinking
  - 闃叉 thinking 鍐呭鐮村潖 JSON 瑙ｆ瀽瀵艰嚧鍚庡彴浠诲姟澶辫触

- **淇敼** `backend/api/mistakes.py` 鈥?璁查杈撳嚭
  - `explain_mistake()` 鍦?`sanitize_latex()` 涔嬪墠鍏堣皟鐢?`strip_thinking()`

**鍘熷垯**锛歵hinking 杩囨护鍙斁鍦?*闈㈠悜鐢ㄦ埛**鎴?*浼氳 JSON 瑙ｆ瀽**鐨勬渶缁堣緭鍑鸿矾寰勶紝瑙勫垝鑺傜偣锛坧lanner锛夌瓑鍐呴儴閾捐矾涓嶆敼銆?

#### Bug 2锛氫緥棰橀骞插彫鍥炵巼涓嶈冻

**鏍瑰洜**锛歁inerU chunk 鍒囧垎鎶婇暱渚嬮鎷嗕负澶氫釜 chunk锛堥骞?+ 姝ラ锛夈€侹G 绮剧‘鍛戒腑 `example` chunk 鏃跺彧鍙栧墠鍚庡悇1涓?chunk锛屼笖棰樺共 chunk 鐨?role 鍙兘琚爣涓?`reference`/`definition`锛屽鑷?`example` 杩囨护鍚庨骞蹭涪澶便€?

**淇**锛氫笁灞傚寮猴紝浠?KG 绮剧‘鍛戒腑鍒板悜閲忔绱㈠叏瑕嗙洊銆?

- **淇敼** `knowledge/knowledge_graph.py`
  - `get_concept_chunks()`锛氬懡涓?role=`example` 鏃讹紝绐楀彛浠?`window=1` 鑷姩澧炲ぇ鍒?`window=3`
  - `_get_nearby_chunks()`锛氬綋 role=`example` 鏃讹紝**鍚戝墠杩芥函**鏈€澶?涓?chunk锛岀洿鍒版壘鍒颁互"渚媂.X"寮€澶寸殑棰樺共 chunk
  - 鏂板 `_EXAMPLE_MARKER_RE` 姝ｅ垯鍖归厤棰樺共鏍囪

- **淇敼** `graph/retrieval_node.py`
  - `_vector_retrieval()`锛氬綋 role 杩囨护鍛戒腑 `example` 鏃讹紝**棰濆鍋氫竴娆℃棤杩囨护鎼滅储**锛坄example_boost`锛夛紝鎶婂彲鑳借閿欐爣鐨勯骞?chunk 涔熷甫鍥炴潵
  - `_merge_and_rerank()`锛氭斁瀹戒笂闄?`max_total_chunks: 8鈫?0`锛宍max_chunks_per_chapter: 5鈫?`

#### Bug 3锛氳嚜琛屾瀯閫犱緥棰樻椂鏁翠釜渚嬮鍙樼孩锛屽叕寮忔棤娉曟樉绀?

**鏍瑰洜**锛歀LM 鏋勯€犱緥棰樻椂甯告妸涓枃鎻忚堪鍖呭湪 `$$` 鎴?`$` 鍐咃紙濡?`$$姹傚嚱鏁?f(x)=x^2 鐨勬瀬灏忓€?$`锛夈€俙sanitize_latex` 鐨?涓枃鍓嶄紭鍏堥棴鍚?閫昏緫鍦ㄤ腑鏂囧墠寮哄埗闂悎瀹氱晫绗︼紝浜х敓**绌哄叕寮?*锛堝 `$$$$`锛夛紝瀵艰嚧 KaTeX 鎶婂悗缁墍鏈夊唴瀹瑰悶鍏ユ暟瀛︽ā寮忥紝鏁存鍙樼孩銆?

**淇**锛歚utils/latex_sanitizer.py` 鈥?`_balance_math_delimiters()`
- 鏂板 `_first_non_whitespace()` 杈呭姪鍑芥暟
- 褰?`$$` 鎴?`$` 鍚庣殑**绗竴涓潪绌虹櫧瀛楃灏辨槸涓枃**鏃讹紝鍒ゅ畾涓?瀹氱晫绗﹁鐢?
- 鎵惧埌閰嶅鐨勭粨鏉熷畾鐣岀锛屾妸涓棿鍐呭**浣滀负鏅€氭枃鏈緭鍑?*锛堝幓鎺夊畾鐣岀锛夛紝涓嶅啀璇曞浘闂悎
- 鍐呭眰鐨?`$...$` 浠嶄細鍦ㄥ悗缁惊鐜腑琚纭鐞?

#### 浣撻獙浼樺寲锛氶潪娴佸紡妯″紡涓嬬殑"鎬濊€冧腑"鏍囧織

**鑳屾櫙**锛氬綋鍓嶅墠绔负璋冭瘯鏂逛究寮€鍚簡闈炴祦寮忔ā寮忥紙`USE_NON_STREAMING = true`锛夛紝鐢ㄦ埛鍙戦€佹秷鎭悗娌℃湁浠讳綍瑙嗚鍙嶉锛岀洿鍒板悗绔繑鍥炲畬鏁寸粨鏋溿€?

**淇**锛?
- `frontend/src/hooks/useChat.ts` 鈥?鍗犱綅娑堟伅 content 浠?`'馃攳 妫€绱腑...'` 鏀逛负 `''`锛宻tage 鏀逛负 `'thinking'`
- `frontend/src/components/ChatMessage.tsx` 鈥?鏂板 `stage` prop锛涘綋 `stage === 'thinking'` 涓?content 涓虹┖鏃讹紝鏄剧ず鏃嬭浆鍔ㄧ敾 + "鎬濊€冧腑鈥?鏂囧瓧
- `frontend/src/pages/ChatPage.tsx` 鈥?鍚?`ChatMessage` 浼犻€?`stage`

#### 鏂囦欢鍙樻洿

| 鏂囦欢 | 鏀瑰姩 |
|------|------|
| `utils/thinking_filter.py` | **鏂板**锛氭祦寮?闈炴祦寮?thinking 杩囨护鍣?|
| `utils/latex_sanitizer.py` | 瀹氱晫绗﹀寘涓枃鏃剁洿鎺ュ幓鎺夎瀵瑰畾鐣岀锛岄伩鍏嶇┖鍏紡 |
| `graph/main_graph.py` | teach/generate 娴佸紡杈撳嚭搴旂敤 ThinkingFilter |
| `graph/generator.py` | 闈炴祦寮忚緭鍑哄簲鐢?strip_thinking |
| `graph/chapter_subgraph.py` | 鍚庡彴 JSON 浠诲姟搴旂敤 strip_thinking |
| `backend/api/mistakes.py` | 璁查杈撳嚭搴旂敤 strip_thinking |
| `knowledge/knowledge_graph.py` | example 绐楀彛澧炲ぇ + 鍚戝墠杩芥函棰樺共 |
| `graph/retrieval_node.py` | example 鍚戦噺妫€绱㈠仛鏃犺繃婊?boost |
| `frontend/src/hooks/useChat.ts` | 鍗犱綅娑堟伅鏀逛负绌哄唴瀹?+ stage='thinking' |
| `frontend/src/components/ChatMessage.tsx` | 鏂板 stage prop + 鎬濊€冧腑鍔ㄧ敾 |
| `frontend/src/pages/ChatPage.tsx` | 鍚?ChatMessage 浼犻€?stage |

#### Bug 4锛歵each 鎰忓浘杩斿洖"鏈寚瀹氱珷鑺?

**鐜拌薄**锛氱敤鎴烽棶"缁欐垜璁蹭竴涓嬪崟绾舰娉曠殑杩唬姝ラ"锛屽洖澶嶆槸"鏈寚瀹氱珷鑺?锛屼絾鏈熬鍗存爣娉ㄤ簡绔犺妭鍚?`鈥?涓夈€佸崟绾舰娉曠殑杩唬姝ラ`銆?

**鏍瑰洜锛堜袱灞傚彔鍔狅級**锛?
1. **plan_node 鎶?灏忚妭鏍囬"閿欏綋鎴?绔犺妭鍚?**锛歀LM 鐪嬪埌"宸茬煡绔犺妭"鍒楄〃鍚庯紝鎶婄敤鎴烽棶棰樹腑鐨勫皬鑺傛爣棰?`"涓夈€佸崟绾舰娉曠殑杩唬姝ラ"` 浣滀负 `target_chapters` 杩斿洖銆備絾鍚戦噺搴撶储寮曢敭鏄?*绔犳爣棰?*锛堝 `"绗?绔?鍗曠函褰㈡硶"`锛夛紝灏忚妭鏍囬涓嶅湪绱㈠紩涓紝`get_chapter_store()` 鎵句笉鍒板搴?collection锛岃繑鍥炵┖ docs銆?
2. **鎵句笉鍒板唴瀹规椂纭繑鍥為敊璇俊鎭?*锛歚chapter_subgraph_run` 鍦?`content == "锛堟棤鍐呭锛?` 鏃惰繑鍥?`{"teaching_content": "鏈寚瀹氱珷鑺?}`锛宍generate_node` 鐩存帴澶嶇敤锛屼笉鍐嶅皾璇曠敤妫€绱㈢鐗囩敓鎴愬洖绛斻€?

**淇**锛?

- **淇敼** `graph/chapter_subgraph.py` 鈥?`prepare_chapter_subgraph()`
  - 鏂板**妯＄硦鍖归厤 fallback**锛氬綋 `search_chapter` 鎸夌簿纭珷鑺傚悕鎵句笉鍒版椂锛岃嚜鍔ㄨ皟鐢?`search_all` 鍋氬叏搴撹涔夋悳绱紝鎵惧埌鏈€鐩稿叧鐨勭湡瀹炵珷鏍囬锛屽啀閲嶆柊妫€绱?
  - `chapter_subgraph_run()`锛氭壘涓嶅埌鍐呭鏃惰繑鍥?`teaching_content: ""`锛堢┖瀛楃涓诧級锛岃€岄潪 `"鏈寚瀹氱珷鑺?`

- **淇敼** `graph/main_graph.py` 鈥?`run_graph_stream()`
  - 鍚屾牱锛氭壘涓嶅埌鍐呭鏃惰缃?`state["teaching_content"] = ""`锛岃鍚庣画 generate 闃舵 fallback 鍒版甯?QA 娴佺▼

- **淇敼** `graph/planner.py` 鈥?`INTENT_PROMPT`
  - prompt 涓槑纭害鏉燂細`target_chapters` 蹇呴』鏄?宸茬煡绔犺妭"鍒楄〃涓殑**绮剧‘鍚嶇О**锛岀姝㈣繑鍥炲皬鑺傛爣棰樻垨鑷鏋勯€?

**fallback 閾捐矾**锛?
```
绮剧‘绔犺妭鍖归厤澶辫触 鈫?鍏ㄥ簱璇箟鎼滅储鎵剧浉鍏崇珷鑺?鈫?鐢ㄦ绱㈠埌鐨勭鐗囧唴瀹圭敓鎴愬洖绛?
                    鈫?浠嶅け璐?
              teaching_content="" 鈫?generate_node 璧版甯?QA 娴佺▼锛堝熀浜?chapter_contents锛?
```

---
## v0.6.6 鈥?2026-06-12

### Bug 淇锛氬唴瀹归噸澶嶆嫾鍑?+ LaTeX 涓嶆樉绀?

#### Bug 1锛氭枃瀛楀叏閮ㄧ敓鎴愬悗娑堝け锛屽彧鍓╁紩鐢紙绗竴杞慨澶嶏級

**鏍瑰洜**锛歚frontend/src/hooks/useChat.ts` 涓?`updateLastMessage` 浣跨敤鍑芥暟寮忔洿鏂般€俁eact 18 鑷姩鎵瑰鐞嗗涓?SSE 浜嬩欢鏃讹紝鎵€鏈?updater 鍑芥暟鐪嬪埌鐨?`last` 閮芥槸**鍚屼竴涓師濮嬬姸鎬佸璞?*锛坄content='馃攳 妫€绱腑...', stage='plan'`锛夈€傛瘡涓?generate 浜嬩欢閮借Е鍙?`last.stage !== 'generate' 鈫?content = ''`锛屾渶缁堝彧淇濈暀鏈€鍚庝竴涓?chunk銆?

**绗竴杞慨澶嶏紙閿欒锛?*锛氬紩鍏ラ棴鍖呭彉閲?`accumulatedContent` 鍦ㄧ粍浠跺绱Н瀹屾暣鍐呭銆傛瘡娆?`updateLastMessage` 鐩存帴璁剧疆 `newMsg.content = accumulatedContent`銆?

**绗簩杞慨澶嶏紙姝ｇ‘锛?*锛歚accumulatedContent` 闂寘鍙橀噺鍦?React StrictMode 寮€鍙戠幆澧冧笅浼氳澶氭鎵ц锛屽鑷村悓涓€浠藉唴瀹硅閲嶅杩藉姞 2~3 娆★紝鍑虹幇"涓夊洓浠藉唴瀹规嫾鍑戝湪涓€璧?鐨勭幇璞°€?

姝ｇ‘鍋氭硶鏄洖褰?React 鍑芥暟寮忔洿鏂扮殑鏈川鈥斺€擿last` 鍙傛暟鍦ㄤ緷娆℃墽琛屾椂纭疄鏄笂涓€涓?updater 鐨勮繑鍥炲€硷細

```javascript
// 鏈€缁堟纭柟妗堬細鐩存帴鐢?last.content 杩藉姞
if (last.stage === 'generate' && event.chunk) {
    newMsg.content = last.content + event.chunk;
} else if (event.chunk) {
    newMsg.content = event.chunk;  // 绗竴涓?generate 浜嬩欢
}
```

鍏抽敭鐐癸細React 18 鑷姩鎵瑰鐞嗗彧鍚堝苟**鍚屼竴浜嬩欢寰幆**涓殑澶氫釜 `setState` 涓轰竴娆℃覆鏌擄紝浣?updater 鍑芥暟浠嶇劧**渚濇鎵ц**锛屾瘡涓嚱鏁扮湅鍒扮殑 `last` 閮芥槸涓婁竴涓?updater 鐨勮繑鍥炲€笺€傛墍浠?`last.content` 濮嬬粓鏄渶鏂扮殑绱Н鍐呭銆?

#### Bug 2锛歀aTeX 鍏紡鐩存帴涓嶆樉绀?

**鏍瑰洜**锛歚package.json` 宸插畨瑁?`react-markdown` + `remark-math` + `rehype-katex` + `katex`锛屼絾 `ChatMessage.tsx` 鍗寸敤 `marked` + `DOMPurify` 鎵嬪姩鎷?HTML锛屽畬鍏ㄧ粫杩囦簡 KaTeX 娓叉煋绠＄嚎銆俙marked` 涔熶笉鍦?`package.json` 渚濊禆涓紙鍙兘鏄棿鎺ヤ緷璧栵級锛屼笖鏂扮増榛樿寮傛杩斿洖 `Promise`锛岃 `DOMPurify.sanitize` 鍚庡彉鎴?`"[object Promise]"` 鎴栫洿鎺ョ┖瀛楃涓层€?

**淇**锛氶噸鍐?`ChatMessage.tsx`锛屼娇鐢ㄩ」鐩凡鏈夌殑 `react-markdown` + `remark-math` + `rehype-katex` 鏍囧噯鏂规锛?
- `remarkMath` 璇嗗埆 `$...$` / `$$...$$` 璇硶
- `rehypeKatex` 閰嶇疆 `strict: false, throwOnError: false`锛岄伩鍏嶆暟瀛﹁〃杈惧紡瑙ｆ瀽閿欒鏃舵暣娈垫秷澶?
- 瀵煎叆 `katex/dist/katex.min.css` 鎻愪緵瀛椾綋鍜屾牱寮?
- 绉婚櫎 `prose` 绫伙紙鏈畨瑁?`@tailwindcss/typography` 鎻掍欢锛夛紝鏀圭敤鑷畾涔?Markdown 缁勪欢鏍峰紡
- 澶栧眰瀹瑰櫒娣诲姞 `whitespace-pre-wrap`锛屼繚鐣欏悗绔崲琛屾牸寮?

**鏂囦欢鍙樻洿**锛?
| 鏂囦欢 | 鏀瑰姩 |
|------|------|
| `frontend/src/hooks/useChat.ts` | 鏈€缁堜慨澶嶏細鐩存帴鐢?`last.content` 杩藉姞锛屾浛浠ｆ湁闂鐨?`accumulatedContent` 闂寘鍙橀噺 |
| `frontend/src/components/ChatMessage.tsx` | 瀹屽叏閲嶅啓锛氱Щ闄?`marked`/`DOMPurify`锛屾敼鐢?`react-markdown` + `remark-math` + `rehype-katex` + 鑷畾涔夌粍浠?|

---
## v0.6.5 鈥?2026-06-12

### 鎸夎涔夎鑹叉绱紙Role-Based Retrieval锛?

**鑳屾櫙**锛歁inerU 棰勫鐞嗛樁娈靛凡涓烘瘡涓?chunk 鎵撲笂浜嗚涔夎鑹叉爣绛撅紙definition / theorem / example / algorithm / derivation 绛夛級锛屼絾鍚戦噺妫€绱粠鏈埄鐢ㄨ繖涓€淇℃伅銆傞棶"浠€涔堟槸姊害涓嬮檷娉?鏃讹紝鍙兘杩斿洖 algorithm 姝ラ chunk 鑰岄潪 definition chunk銆?

**鍏抽敭鍙戠幇**锛氬垎鏋?occurrence 鏁版嵁鍚庡彂鐜帮紝**565 涓?chunk 鐨?role 瀹屽叏涓€鑷?*锛坢ulti-role chunks = 0锛夛紝璇存槑 chunk 宸插ぉ鐒舵寜璇箟瑙掕壊鍒嗗ソ銆?

**鏂规**锛氫笉鏀瑰垏鍒嗙瓥鐣ワ紝鍙湪妫€绱㈤樁娈靛埄鐢ㄥ凡鏈夌殑 role metadata銆?

#### 鏀瑰姩璇︽儏

- **鏂板** `knowledge_graph.py` 鈥?`_chunk_role` 绱㈠紩
  - 浠?occurrence 鏁版嵁鎻愬彇姣忎釜 chunk_id 鐨勪富瑙掕壊
  - 鍏?565 涓?chunk 鏈?role 鏍囨敞锛屽垎甯冿細reference(251) / algorithm(96) / example(73) / definition(68) / derivation(43) / exercise(14) / property(11) / theorem(8) / proof(1)

- **淇敼** `ingestion/vector_store.py` 鈥?鏀寔 role metadata 鍜岃繃婊ゆ绱?
  - `build_chapter_store()` 鏂板 `chunk_roles` 鍙傛暟锛屽皢 role 鍐欏叆 document metadata
  - `search_chapter()` / `search_all()` 鏂板 `filter` 鍙傛暟锛屾敮鎸?`{"role": "definition"}` 鏍煎紡杩囨护

- **淇敼** `graph/retrieval_node.py` 鈥?鎸?intent 鈫?role 浼樺厛绾ц繃婊?
  - 鏂板 `INTENT_ROLE_PRIORITY` 鏄犲皠锛歞efinition 浼樺厛鎼?definition鈫抰heorem鈫抪roperty鈫抏xample鈫抎erivation锛沘pplication 浼樺厛鎼?example鈫抋lgorithm鈫抏xercise鈫抎erivation
  - `_vector_retrieval()` 浼犲叆 intent锛岃嚜鍔ㄦ寜浼樺厛绾у皾璇?role 杩囨护锛屾棤缁撴灉鍒欏洖閫€鍒版棤杩囨护
  - 鏂板 `_search_chapter_with_role()` / `_search_all_with_role()` 杈呭姪鍑芥暟

- **鏂板** `scripts/rebuild_index_with_roles.py` 鈥?閲嶅缓绱㈠紩鑴氭湰
  - 浠?`mineru_output/<book>/hybrid_auto/<book>_middle_chunks.json` 璇诲彇鍘熺敓 chunk 鏁版嵁
  - 浣跨敤 MinerU 鍘熺敓 chunk_id锛堝 `p20_c54`锛夛紝涓?KG occurrence 鐨?chunk_id 瀹屽叏涓€鑷?
  - 涔嬪墠绱㈠紩鐨?chunk_id 鏄?`hashlib.md5(...)` 鑷缓鏍煎紡锛屼笌 KG 涓嶅尮閰嶏紝瀵艰嚧 role 鍏ㄩ儴 fallback 鍒?reference

- **淇敼** `graph/generator.py` 鈥?渚嬮瀹屾暣鎬?prompt 鏇存柊
  - 妫€娴嬪埌渚嬮鏍囪鏃讹細娉ㄥ叆瀹屾暣鑷娴佺▼
  - 鏃犱緥棰樻爣璁版椂锛氬厑璁?LLM 鍩轰簬妫€绱㈡蹇佃嚜琛屾瀯閫犵瓑鏁堜緥棰橈紙椤绘爣娉╗琛ュ厖渚嬮]銆佹牳蹇冩蹇典竴鑷淬€侀毦搴︾浉褰撱€佺鍙蜂竴鑷达級

#### 閲嶅缓绱㈠紩鍛戒护
```powershell
cd D:/AI/agent/kaoyan-assistant
. venv310/Scripts/activate
python scripts/rebuild_index_with_roles.py --book_name 浼樺寲璁捐
```

---
## v0.6.4 鈥?2026-06-12

### Bug 淇锛氫緥棰橀骞插够瑙?+ 闀垮唴瀹瑰璇濇娑堝け

#### Bug 1锛氫緥棰橀骞蹭笉鏄剧ず / LLM 骞昏鑴戣ˉ棰樺共

**鏍瑰洜**锛?
1. 鍚戦噺妫€绱㈠彧杩斿洖璇箟鏈€鐩镐技鐨?chunk锛屼緥棰樿鍥哄畾闀垮害鍒囧垎鍚庨骞?瑙ｆ硶鍒嗘暎鍦ㄤ笉鍚?chunk
2. Prompt 铏芥湁"涓嶅緱缂栭€?绾︽潫锛屼絾娌℃湁鏄庣‘鍛婅瘔 LLM 濡備綍鍒ゆ柇棰樺共鏄惁瀹屾暣

**淇**锛?
- **鏂板** `graph/generator.py` 鈥?`_has_example_marker()` 鍑芥暟锛屾娴嬫绱㈠唴瀹逛腑鏄惁鍖呭惈"渚媂.X"绛変緥棰樻爣璁?
- **淇敼** `graph/generator.py` 鈥?prompt 鍔ㄦ€佹敞鍏ヤ緥棰樺畬鏁存€ц嚜妫€锛?
  - 妫€娴嬪埌渚嬮鏍囪鏃讹細娉ㄥ叆瀹屾暣鑷娴佺▼锛?妫€鏌ユ槸鍚︽湁瀹屾暣棰樺共 鈫?鏈夊垯澶嶈堪+鎷嗚В锛屾棤鍒欏彧璁叉蹇?锛?
  - 鏈娴嬪埌渚嬮鏍囪鏃讹細娉ㄥ叆绠€鍖栫害鏉燂紙"涓嶅緱缂栭€犱笉瀛樺湪鐨勯骞?锛?
- **鏂板** `tests/test_generator.py` 鈥?3 涓崟鍏冩祴璇曡鐩栨爣璁版娴嬨€佽嚜妫€娉ㄥ叆銆乫allback 绾︽潫

#### Bug 2锛氳秴鍑轰竴瀹氬瓧鏁版椂瀵硅瘽妗嗘秷澶憋紝鍙樻垚"妫€绱腑"

**鏍瑰洜**锛歚frontend/src/hooks/useChat.ts` 涓娇鐢ㄩ棴鍖呭彉閲?`contentStarted` 鍒ゆ柇鏄惁鏄涓€涓?generate 浜嬩欢銆俁eact 18 鑷姩鎵瑰鐞嗗涓?SSE 浜嬩欢鏃讹紝闂寘鍙橀噺琚彁鍓嶇疆浣嶏紝瀵艰嚧鍚庣画 updater 鍑芥暟鍩轰簬杩囨湡鐘舵€佹墽琛岋紝content 琚噸缃负"妫€绱腑..."鍓嶇紑銆?

**淇**锛?
- **淇敼** `frontend/src/hooks/useChat.ts` 鈥?鐢?`last.stage`锛堢姸鎬佺殑涓€閮ㄥ垎锛夋浛浠?`contentStarted` 闂寘鍙橀噺锛孯eact 鐨勫嚱鏁板紡鏇存柊淇濊瘉姣忔閮借兘璇诲彇鍒版渶鏂扮姸鎬?
- **鏂板** `frontend/src/components/ErrorBoundary.tsx` 鈥?React 閿欒杈圭晫缁勪欢锛屾崟鑾?ChatMessage 娓叉煋寮傚父锛岄槻姝㈡暣椤靛穿婧?
- **淇敼** `frontend/src/pages/ChatPage.tsx` 鈥?鐢?ErrorBoundary 鍖呰９姣忔潯娑堟伅锛屾覆鏌撳け璐ユ椂鏄剧ず鍙嬪ソ鎻愮ず鑰岄潪鐧藉睆

---
## v0.6.3 鈥?2026-06-12

### 妫€绱㈢瓥鐣ュ崌绾э細涓夊眰娣峰悎妫€绱?

**闂**锛氱函鍚戦噺妫€绱㈠瓨鍦?璇箟婕傜Щ"鈥斺€旈棶"KKT鏉′欢"鍙兘杩斿洖"绾︽潫浼樺寲姒傝堪"娉涙硾浠嬬粛锛屼絾娌″懡涓?KKT 瀹氫箟鎵€鍦ㄧ殑绮剧‘ chunk銆?

**鏂规**锛氶噸鏋?`graph/retrieval_node.py` 涓轰笁灞傛贩鍚堟绱€?

#### 鏀瑰姩璇︽儏

- **鏂板** `knowledge_graph.py` 鈥?`get_concept_chunks()` / `_get_nearby_chunks()`
  - 閫氳繃 occurrence 鐨?`chunk_id` 绮剧‘瀹氫綅姒傚康瀹氫箟鎵€鍦ㄦ钀?
  - 鍙栧墠鍚?涓?chunk 婊戝姩绐楀彛锛屼繚璇佷笂涓嬫枃杩炶疮
  - 鎸?`role` 浼樺厛绾ф帓搴忥紙definition > theorem > property > ...锛夛紝浼樺厛杩斿洖瀹氫箟/瀹氱悊鎵€鍦ㄤ綅缃?
  - `max_hits` 鍙傛暟闄愬埗楂橀姒傚康鐨?chunk 鏁伴噺锛堥粯璁?锛夛紝閬垮厤 prompt 鑶ㄨ儉

- **閲嶆瀯** `graph/retrieval_node.py` 鈥?涓夊眰娣峰悎妫€绱㈤€昏緫
  - **L1 KG 绮剧‘鍛戒腑**锛歚kg.search_concept()` 鈫?`kg.get_concept_chunks()`锛岀疆淇″害闃堝€?鈮?0
  - **L2 鍚戦噺琛ュ厖**锛氫紭鍏堝湪 L1 鍛戒腑绔犺妭鍐呮悳绱紝鏃犲懡涓椂鍏ㄥ簱鎼滅储
  - **L3 鍘婚噸閲嶆帓**锛氱簿纭懡涓?chunk 鎺掓渶鍓嶏紝鍚戦噺缁撴灉鍘婚噸鎺ュ悗锛涙瘡绔犳渶澶?涓?chunk锛屽叏灞€鏈€澶?涓?
  - 鏂板杩斿洖瀛楁锛歚knowledge_graph_formulas`锛堢浉鍏冲叕寮忥級銆乣matched_concepts`锛堝懡涓蹇靛悕锛?

- **淇敼** `graph/state.py` 鈥?`AgentState` 鏂板 `knowledge_graph_formulas` 鍜?`matched_concepts` 瀛楁

- **鍏煎鎬?*锛氭棤鏈湴 KG 鏁版嵁鏃惰嚜鍔ㄥ洖閫€鍒扮函鍚戦噺妫€绱紝闆朵镜鍏ユ棫璺緞

---
## v0.6.2 鈥?2026-06-12

### 淇 DeepSeek 杈撳嚭涓殑渚嬮棰樺共涓㈠け涓?LaTeX 鎶ョ孩

#### Bug 1锛氶儴鍒嗚鏈緥棰橀骞蹭涪澶便€佸彧鍓╂楠?
**鏍瑰洜**锛歚graph/generator.py` 涓暀鏉?chunk 琚埅鏂埌 500 瀛楃/2 doc锛屽鑷翠緥棰樼殑棰樺共涓庤В棰樻楠よ鍒囧垎锛孡LM 鍙兘鐪嬪埌涓嶅畬鏁寸墖娈点€?
**淇**锛?
- **淇敼** `graph/generator.py` 鈥?鍗曚釜 doc 鎴柇浠?500 瀛楃鎻愬崌鍒?1500 瀛楃锛屾瘡绔犺妭浣跨敤 doc 鏁颁粠 2 鎻愬崌鍒?3
- **淇敼** `graph/generator.py` / `graph/chapter_subgraph.py` 鈥?prompt 澧炲姞绾︽潫锛?鑻ユ绱㈠埌鐨勪緥棰橀骞蹭笉瀹屾暣锛屽繀椤诲瀹炶鏄庯紝涓嶅緱缂栭€犵己澶辩殑棰樺共"

#### Bug 2锛氬彞鍐?娈佃惤涓?LaTeX 鏈伒瀹堟牸寮忋€佸叕寮忓強鍚庣画鏂囧瓧鍏ㄧ▼鎶ョ孩
**鏍瑰洜**锛欴eepSeek 鍋跺彂鏈棴鍚?`$` / `$$`锛屾垨杈撳嚭 `\( ... \)` / `\[ ... \]` 瀹氱晫绗︼紝瀵艰嚧 remark-math/KaTeX 鎶婃鏂囧悶杩涙暟瀛︽ā寮忓苟娓叉煋涓虹孩鑹查敊璇€?
**淇**锛?
- **鏂板** `utils/latex_sanitizer.py` 鈥?涓撶敤鍚庡鐞嗗櫒锛?
  - 灏?`\( ... \)` / `\[ ... \]` 杞崲涓?`$...$` / `$$...$$`
  - 鑷姩琛ュ叏鏈棴鍚堢殑 `$` / `$$`
  - 鍦ㄤ腑鏂?涓枃鏍囩偣鍓嶄紭鍏堥棴鍚堬紝閬垮厤姝ｆ枃琚悶鍏ユ暟瀛︽ā寮?
  - 涓嶇牬鍧忓凡姝ｇ‘閰嶅鐨勫叕寮忓拰 `\text{...}` 涓殑涓枃
- **淇敼** `graph/generator.py` / `graph/main_graph.py` / `graph/chapter_subgraph.py` / `backend/api/mistakes.py` 鈥?瀵规墍鏈夐潰鍚戝墠绔殑 LLM 杈撳嚭搴旂敤 `sanitize_latex()`
- **淇敼** `graph/generator.py` / `graph/chapter_subgraph.py` 鈥?prompt 澧炲姞绾︽潫锛?鎵€鏈?$ / $$ 蹇呴』鎴愬闂悎锛屼笉鑳芥妸涓枃鏂囧瓧鎴栨爣鐐瑰寘鍦ㄦ暟瀛︽ā寮忓唴"

#### 娴嬭瘯
- **鏂板** `tests/test_latex_sanitizer.py` 鈥?7 涓崟鍏冩祴璇曡鐩栨湭闂悎琛屽唴/鍧楃骇鍏紡銆乀eX 瀹氱晫绗﹁浆鎹€佹甯稿叕寮忎繚鎶ょ瓑鍦烘櫙
- **鏂板** `tests/test_generator.py` 鈥?3 涓崟鍏冩祴璇曢獙璇?prompt 淇濈暀鏇撮暱涓婁笅鏂囧苟鍖呭惈"涓嶅畬鏁翠緥棰?鎻愮ず

---
## v0.6.1 鈥?2026-06-12

### LLM 鍒囨崲锛欿imi K2.6 鈫?DeepSeek V4 Pro锛堟€濊€冩ā寮忥級
- **淇敼** `config.py` 鈥?鍚庣閫氳繃 `extra_body` 鍚敤 DeepSeek V4 Pro 鎬濊€冩ā寮忥紙`thinking: enabled`, `reasoning_effort: high`锛?
- 瀹炴祴鎻愰€燂細**5-7 鍊?*锛圞imi 158s 鈫?DeepSeek 28s锛宼each 璺緞锛?
- 鏁欐潗 chunk 鍒╃敤鐜囦紭绉€锛氫富鍔ㄥ紩鐢ㄥ叕寮忕紪鍙凤紙寮?-21銆佸紡5-26锛夛紝鏍囨敞鏉ユ簮
- 鎬濊€冩ā寮忚緭鍑烘洿鑱氱劍锛氶潪鎬濊€?6694 瀛?vs 鎬濊€?3392 瀛楋紝璐ㄩ噺涓嶉檷鍙嶅崌

### Prompt 瀛楁暟鎺у埗瑙勫垯閲嶆瀯
- **淇敼** `graph/generator.py` `output_instruction`
  - 瑙ｉ噴鎬ф枃瀛楋紙瀹氫箟/鎬ц川/鎺ㄥ璇存槑锛変弗鏍奸檺鍒跺瓧鏁?
  - **渚嬮/瑙ｉ姝ラ閮ㄥ垎涓嶅彈瀛楁暟闄愬埗** 鈥?鍏紡銆佹暟瀛椼€佽绠楁楠や俊鎭瘑搴︽瀬楂橈紝瀹屾暣灞曞紑鏈夊姪浜庣悊瑙?
  - Teach 璺緞宸查€氳繃缁撴瀯鍖?prompt 鑷劧瀹炵幇锛氳В閲婂帇缂╋紝渚嬮瀹屾暣灞曞紑

### 鍓嶇浣撻獙浼樺寲
- **淇敼** `frontend/src/hooks/useChat.ts` 鈥?generate 寮€濮嬫椂寮哄埗娓呯┖鍗犱綅鏂囧瓧锛屼笉鍐嶆樉绀?妫€绱腑鈥?
- **淇敼** `frontend/src/components/ChatMessage.tsx` 鈥?淇 Markdown 琛ㄦ牸娓叉煋锛屽澶у瓧浣擄紙text-sm 鈫?text-base锛夛紝澧炲姞瀛楅棿璺濓紙tracking-wide锛?
- **淇敼** `frontend/src/index.css` 鈥?娣诲姞 Markdown 鍐呭鍩虹鏍峰紡锛堟浛浠ｆ湭瀹夎鐨?typography 鎻掍欢锛?

### 鏆傛椂鍏抽棴瀛︿範鎻愰啋
- **淇敼** `graph/main_graph.py` 鈥?娉ㄩ噴鎺?ConceptMemory 鍚屾 enrich + 鍚庡彴鎻愬彇閫昏緫

---
## v0.6.0 鈥?2026-06-10

### 鏋舵瀯杩佺Щ锛欸radio 鈫?FastAPI + React

> Gradio 宓屽 Tabs 鍗℃闂鍙嶅鍑虹幇涓旀棤娉曟牴娌伙紝宸插交搴曞純鐢ㄣ€?
> 鏂版灦鏋勫墠鍚庣鍒嗙锛屾牳蹇冮€昏緫锛坄graph/`/`agents/`/`knowledge/`/`memory/`/`ingestion/`锛夐浂鏀瑰姩銆?

#### Phase 1: FastAPI 鍚庣

- **鏂板** `backend/main.py` 鈥?FastAPI 鍏ュ彛 + CORS + 闈欐€佹枃浠舵寕杞?
- **鏂板** `backend/schemas.py` 鈥?Pydantic 璇锋眰/鍝嶅簲妯″瀷
- **鏂板** `backend/api/chat.py` 鈥?SSE 娴佸紡瀵硅瘽锛堝寘瑁?`run_graph_stream`锛?
- **鏂板** `backend/api/mistakes.py` 鈥?閿欓鏈?CRUD + SM-2 澶嶄範 + LLM 璁查
- **鏂板** `backend/api/books.py` 鈥?鏁欐潗鍒楄〃 / 鍒囨崲 / 瀵煎叆 / 棰勮
- **鏂板** `backend/api/kg.py` 鈥?鐭ヨ瘑鍥捐氨鑾峰彇 / 鍒锋柊

#### Phase 2: React 鍓嶇

- **鏂板** `frontend/` 鐩綍锛圴ite + React 18 + TypeScript + Tailwind CSS锛?
- `frontend/src/App.tsx` 鈥?React Router v6 璺敱 + `ChatProvider` 鍏ㄥ眬鐘舵€?
- `frontend/src/contexts/ChatContext.tsx` 鈥?鍏ㄥ眬瀵硅瘽鐘舵€侊紙璺敱鍒囨崲涓嶄涪澶卞璇濊褰曪級
- `frontend/src/api/client.ts` 鈥?HTTP GET/POST + SSE 娴佸紡瀹㈡埛绔?
- `frontend/src/hooks/useChat.ts` 鈥?SSE 娴佸紡瀵硅瘽 hook
- `frontend/src/pages/ChatPage.tsx` 鈥?馃挰 瀵硅瘽椤碉紙Markdown/KaTeX 娓叉煋 + 鑷姩婊氬姩锛?
- `frontend/src/pages/MistakesPage.tsx` 鈥?馃摑 閿欓鏈紙褰曞叆 / 鍒楄〃 / 浠婃棩澶嶄範 / 缁熻锛?
- `frontend/src/pages/KnowledgeGraphPage.tsx` 鈥?馃敆 鐭ヨ瘑鍥捐氨锛坕frame 宓屽叆鐜版湁 HTML锛?
- `frontend/src/pages/BooksPage.tsx` 鈥?馃摜 鏁欐潗瀵煎叆锛圥DF 涓婁紶 + 鐩綍椤电爜 + 棰勮閫夐」锛?

#### 鍏抽敭淇

| 闂 | 淇 |
|------|------|
| Gradio `web.py` 宓屽 Tabs 鍗℃ | **褰诲簳瑙ｅ喅**锛堝純鐢?Gradio锛?|
| 璺敱鍒囨崲瀵硅瘽涓㈠け | `ChatContext` 鍏ㄥ眬鐘舵€佹寔涔呭寲 |
| 閿欓鏈粺璁?Tab 鍏ㄥ睆瑕嗙洊/鐧藉睆 | 娣诲姞 `loading`/`error` 杈圭晫 + 绌哄€间繚鎶?|

#### 鍚姩鏂瑰紡

```powershell
# 鍚庣
cd D:\AI\agent\kaoyan-assistant
.\venv310\Scripts\Activate.ps1
python -m uvicorn backend.main:app --port 8000

# 鍓嶇锛堝彟寮€缁堢锛?
cd D:\AI\agent\kaoyan-assistant\frontend
npm run dev
```

---
## v0.5.0 鈥?2026-06-05

### Teach Prompt 浼樺寲锛氶鐩┍鍔ㄨ瑙?
- **淇敼** `graph/chapter_subgraph.py`
  - 鍘诲瘨鏆勶細鍒犻櫎"鍚屽浣犲ソ锛屾垜鏄綘鐨勮€冪爺瀵煎笀"绫诲紑鍦虹櫧锛岀洿鎺ヨ繘鍏ヨ棰?
  - 棰樼洰鍏堣锛氳瑙ｈ姹備粠"浠庡熀纭€姒傚康寮€濮?鏀逛负"鍏堢粰鍏稿瀷鑰冪爺棰?鏁欐潗渚嬮"
  - 鎬濊矾鎷嗚В锛氭瘡姝ヨ鏄?鍋氫粈涔?+ 涓轰粈涔?锛屾槧灏勫搴旂煡璇嗙偣/鍏紡/瀹氱悊
  - 鍛介鍒嗘瀽锛氳鏄庤€冧粈涔堛€佹槗閿欑偣銆佸懡棰橀櫡闃?
  - ~~鍙樺紡缁冧範锛氱粰涓€閬撶被浼奸锛堝凡绉婚櫎 鈥?鑰冪爺绾у埆棰樼洰闅句互鍑哄彲琛屽彉寮忥紝Quiz 鍔熻兘宸叉斁寮冿級~~
  - 鍏紡閫熸煡锛氭湯灏鹃檮鏍稿績鍏紡 + 甯歌鑰冩硶娓呭崟

### 閿欓鏈牳蹇冨眰锛堝彲澶嶇敤鏋舵瀯锛?
- **鏂板** `memory/mistake_book.py`
  - **闆跺閮ㄤ緷璧?*锛氫粎 sqlite3/datetime/uuid/json锛屽彲鐙珛鎶界鎴愬崟鐙簲鐢?
  - **鏁版嵁妯″瀷**锛歚MistakeRecord`锛堥鐩?绛旀/鏉ユ簮/瀛︾/绔犺妭/鏍囩/閿欏洜/闅惧害/SM-2 鐘舵€侊級
  - **瀛樺偍灞?*锛歚MistakeBookStore`锛圫QLite + 鎸夊绉?绔犺妭/鏍囩/澶嶄範鏃ユ湡绱㈠紩锛?
  - **澶嶄範璋冨害**锛歚SM2Scheduler`锛堝鐢?SM-2 绠楁硶锛岀嫭绔嬬鐞嗛敊棰樺涔犻棿闅旓級
  - **鏍稿績 API**锛歚add/get/review/get_due/get_stats/get_weak_points/explain`
  - **閫傞厤灞傝璁?*锛歚explain()` 閫氳繃 `ContextProvider` 鍥炶皟娉ㄥ叆涓婁笅鏂?
    - 涓撲笟璇炬ā寮忥細娉ㄥ叆 RAG 妫€绱㈢殑鏁欐潗鍘熸枃/鍏紡
    - 閫氱敤妯″紡锛堣嫳璇?鏀挎不/鏁板锛夛細涓嶆敞鍏ワ紝绾?LLM 璁查
  - **棰勭暀鎺ュ彛**锛歚explain_prompt()` 鍙崟鐙彇鍑?prompt锛岀敱璋冪敤鏂硅嚜琛岃皟鐢?LLM

### 閿欓鏈?UI 闆嗘垚锛坄ui/web.py`锛?
- **鏂板** "馃摑 閿欓鏈? 鏍囩椤碉紝鍐呭惈4涓瓙鏍囩锛?
  - **馃摜 褰曞叆**锛氶鐩枃鏈紙LaTeX 鏀寔锛? 鐢ㄦ埛绛旀 / 姝ｇ‘绛旀 / 鏉ユ簮 / 瀛︾ / 鐭ヨ瘑鐐规爣绛?/ 閿欏洜澶氶€?/ 闅惧害婊戝潡 / 鎴浘涓婁紶
  - **馃搵 閿欓鍒楄〃**锛氭寜瀛︾绛涢€?+ 鍏抽敭璇嶆悳绱?/ DataFrame 灞曠ず / 閫変腑 ID 鏌ョ湅璇︽儏 / 涓€閿?LLM 璁查
  - **馃搮 浠婃棩澶嶄範**锛歋M-2 璋冨害灞曠ず浠婃棩寰呭涔犻敊棰?/ 鎺屾彙绋嬪害璇勫垎锛?-5锛夋彁浜ゅ涔?/ 璁查
  - **馃搳 缁熻**锛氭€婚敊棰樻暟 / 浠婃棩寰呭涔?/ 閿欏洜鍒嗗竷 / 钖勫急鐐?TOP 鍒楄〃
- **璁查鍙屾ā寮?*锛?
  - 涓撲笟璇炬ā寮忥細鑷姩璋冪敤 `search_all()` 娉ㄥ叆鐩稿叧鏁欐潗涓婁笅鏂囧埌 LLM prompt
  - 閫氱敤妯″紡锛堣嫳璇?鏀挎不/鏁板锛夛細鏃?RAG 娉ㄥ叆锛岀函 LLM 璁查

---
## v0.4.0 鈥?2026-06-04

### LangGraph 鎺ュ叆 Web UI
- `graph/main_graph.py` 鏂板 `run_graph_stream()` 鈥?娴佸紡椹卞姩 plan 鈫?retrieve 鈫?generate 鈫?feedback
- `ui/web.py` `ask_stream()` 鏀逛负娑堣垂 `run_graph_stream()` 浜嬩欢
- 鍒犻櫎鏃ф柟娉曪細`_detect_intent`銆乣_fast_answer_stream`銆乣_read_and_answer_stream`銆乣_teach_stream`

### 缁嗙矑搴︽剰鍥惧垎绫?+ Fast Path
- **鏂板** `graph/intent_classifier.py`
  - 鏈湴姣绾у垎绫伙細definition/formula/property/derivation/comparison/application/teach/summarize/...
  - Fast Path锛歞efinition/formula/property 璺宠繃 plan LLM锛岀渷 1 娆¤皟鐢?
- **淇敼** `graph/planner.py`
  - 鏀寔 11 绉嶇粏绮掑害鎰忓浘锛屾帴鍙楁湰鍦板垎绫诲櫒鐨?hint 鍑忓皯 LLM 鐚滄祴
- **淇敼** `graph/generator.py`
  - 姣忕鎰忓浘鏈変笓灞?output_instruction锛堝畾涔夊厛缁欏叕寮忓啀缁欒В閲婏紝姣旇緝缁欒〃鏍硷紝鎺ㄥ缁欏畬鏁存楠?..锛?

### ConceptMemory 姒傚康璁板繂绯荤粺
- **鏂板** `knowledge/concept_memory.py`
  - 姒傚康鎻愬彇锛圠LM + 鏈湴 fallback锛?
  - 鎺ヨЕ璁板綍锛堥鐜囥€佹椂闂存埑銆佷笂涓嬫枃锛?
  - 閬楀繕妫€娴嬶紙楂橀浣嗕箙鏈帴瑙?鈫?鎻愰啋锛?
  - 瀛︿範鎻愰啋锛堝洖绛旀湯灏鹃檮鍔?馃挕/馃尡 鎻愰啋锛?
  - **棰勭暀鎺ュ彛**锛歚mark_weak()`銆乣get_weak_points()`銆乣get_review_queue()`锛堜緵閿欓鏈?鍛ㄦ湡鎬у洖椤捐皟鐢級
- **淇敼** `graph/main_graph.py`
  - `run_graph_stream()` 鍦?generate 鍚庤嚜鍔ㄨ皟鐢?ConceptMemory
  - 鍚庡彴寮傛 LLM 鎻愬彇 + 鍚屾鏈湴 enrich

#### 楠岃瘉缁撴灉
```
"浠€涔堟槸姊害涓嬮檷娉?      鈫?intent=definition,  fast_path=True  鉁?
"姊害涓嬮檷鍜岀墰椤挎硶鐨勫尯鍒? 鈫?intent=comparison,  fast_path=False 鉁?
"璇佹槑姊害涓嬮檷鐨勬敹鏁涙€?  鈫?intent=derivation,  fast_path=False 鉁?
```

---
## v0.3.0 鈥?2026-06-03

### 鎬ц兘浼樺寲锛歍each 璺緞 LLM 璋冪敤鍚堝苟
- **淇敼** `graph/chapter_subgraph.py`
  - 鍏抽敭璺緞浠?2-3 娆?LLM 闄嶄负 1 娆★紙璁茶В + 鎬荤粨鍚堝苟涓哄崟娆¤皟鐢級
  - 鎻愬彇閲嶇偣銆佸嚭棰樻敼涓哄悗鍙?`ThreadPoolExecutor` 骞惰锛屼笉闃诲涓绘祦绋?

### 鏋舵瀯鍒嗘瀽
- 瀹氫綅鐡堕锛歈A Path 2-5 绉掞紙鑹ソ锛夛紝Teach Path 4-8 绉掞紙涓瓑锛?
- 褰撳墠鐘舵€侊細Web UI 涓嶅啀缁曡繃 Main Graph锛岀洿鎺ユ秷璐?`run_graph_stream()` 娴佸紡浜嬩欢

---
## v0.2.0 鈥?2026-05-31 ~ 06-02

### 鏁版嵁灞傚缓璁?
- **鏂板** `ingestion/pdf_parser.py` 鈥?PDF 鈫?TOC锛屼紭鍏堢敤 Kimi Vision 妫€娴嬬洰褰?
- **鏂板** `ingestion/chapter_splitter.py` 鈥?鎸夌珷鑺?鏍囬鍒嗗潡
- **鏂板** `ingestion/vector_store.py` 鈥?ChromaDB 鍚戦噺瀛樺偍锛堢珷鑺傞殧绂荤储寮曪級
- **鏂板** `knowledge/summary_store.py` 鈥?绔犺妭鎽樿缂撳瓨锛圝SON 鎸佷箙鍖栵級
- **鏂板** `memory/spaced_repetition.py` 鈥?SM-2 闂撮殧閲嶅绠楁硶

### 鍒濆 RAG Pipeline
- `graph/retrieval_node.py` 鈥?澶氳矾妫€绱紙鍚戦噺 + 鍏抽敭璇?+ 绔犺妭杩囨护锛?
- `graph/generator.py` 鈥?缁煎悎鐢熸垚锛堟暣鍚堟绱㈢粨鏋?+ 鏁欏浜у嚭 + 鐭ヨ瘑鍥捐氨锛?
- `graph/planner.py` 鈥?绮楃矑搴︽剰鍥惧垎绫伙紙qa / teach / quiz / plan锛?

---
## v0.1.0 鈥?2026-05-30

### 椤圭洰鍒濆鍖?
- 鍩虹鐩綍缁撴瀯
- `config.py` 鈥?LLM/宓屽叆/璺緞閰嶇疆
- `ui/web.py` 鈥?Claude 椋庢牸 WebUI锛圙radio锛?
- `ui/cli.py` 鈥?鍛戒护琛岀晫闈?
- `main.py` 鈥?缁熶竴鍏ュ彛锛坄python main.py web --port 8080`锛?

---
## Docker deployment MVP - 2026-06-26

### Added
- Added `Dockerfile` with a multi-stage build: React/Vite frontend build, then Python 3.10 FastAPI runtime.
- Added `docker-compose.yml` for one-container full-stack deployment on port 8000.
- Added `.dockerignore` to keep local data, virtualenvs, secrets, build outputs, and scratch files out of the image.
- Added `scripts/docker-entrypoint.sh` to create local data subdirectories inside the mounted `/app/data` volume before startup.
- Added `scripts/backup-docker-data.ps1` to zip the host `data/` directory before updates.
- Added `scripts/update-docker.ps1` to backup data, build/pull image, restart compose, and check `/health`.
- Added `docs/docker_deploy.md` with first-start, update, backup, rollback, and MinerU/OCR external API notes.

### Changed
- `config.py` now supports `DATA_DIR` and env-overridable `PROGRESS_PATH`, while keeping existing relative paths working.
- Embedding cache now uses `DATA_DIR/models`; Docker sets `EMBEDDING_LOCAL_FILES_ONLY=0` so a fresh machine can download the embedding model into the host-mounted data directory.
- `requirements.txt` now explicitly includes Docker runtime web dependencies: `fastapi`, `uvicorn[standard]`, and `python-multipart`.
- `.env.example` now documents `DATA_DIR`, `PROGRESS_PATH`, `EMBEDDING_LOCAL_FILES_ONLY`, and optional `MINERU_API_URL` / `OCR_API_URL`.

### Deployment model locked in
- Docker image contains only program code and fixed dependencies.
- User data remains on the host under `./data` and is mounted into the container as `/app/data`.
- New users start with empty local data, import their own textbooks, and generate Chroma/study records locally.
- MinerU and OCR are optional external HTTP services, not bundled into the main image.
- Updating or deleting the container must not delete `./data`.

### Verification
- `npm run build` passed for the frontend production build.
- `backend.main` imports successfully with the current local environment.
- `config.py` resolves `DATA_DIR` paths correctly in a local smoke check.
- Docker real build was not run because `docker` is not installed/available in the current environment. Next continuation step: run `docker compose config` and `docker compose build` on a machine with Docker.


---
## New-user clean deployment packaging - 2026-06-26

### Added
- Added `docs/new_user_deploy.md` for clean-machine deployment where the new user starts without local textbooks, Chroma indexes, mistakes, or study records.
- Added `docs/project_layout.md` to clarify source directories, deployment files, test/docs areas, and local-only runtime data.
- Added `scripts/export-new-user-package.ps1`, which creates a clean source package from tracked files plus non-ignored untracked source files.

### Changed
- Added `exports/` to `.gitignore` and `.dockerignore` so generated migration packages do not enter Git or Docker build contexts.

### Notes
- Clean new-user packages exclude `.env`, API key files, `data/`, virtual environments, frontend dependency/build artifacts, caches, logs, backups, and scratch diagnostics.
- Personal learning data migration remains a separate explicit choice; the default new-user package starts with empty local data.

### Follow-up
- Added `pytest.ini` so pytest only collects `tests/` and ignores generated export packages, local data, virtual environments, frontend dependency/build folders, caches, and logs.


---
## Local directory cleanup - 2026-06-26

### Removed
- Removed obsolete root-level diagnostic and benchmark scratch files: `_benchmark*.py`, `_test_*.py`, `_test_*.md`, `_test_*.json`, `_output.txt`, `_show*.txt`, `_show*.py`, `_check_chunks.py`, `_smoke_test.txt`.
- Removed old one-off OCR/TOC outputs: `kimi_toc.json`, `ocr_p6.json`, `ocr_p6_full.txt`.
- Removed old session archive `session_*.zip`.
- Removed obsolete root-level manual scripts that are not part of the current FastAPI/React/Docker flow: `check_toc.py`, `test_chapters.py`, `test_splitter.py`, `ingest_mineru.py`.
- Removed local Python test/cache directories `.pytest_cache/` and root `__pycache__/`.

### Kept
- Kept `scripts/rebuild_index_with_roles.py` because it is still the current manual role-aware Chroma rebuild utility.
- Kept `install.ps1`, `launch.ps1`, `??Web.bat`, and `??CLI.bat` as local startup/install helpers.
- Kept `.env`, `deepseek-api.txt`, `data/`, virtual environments, and dependency folders; these are local-only but not obsolete.

### Follow-up
- Disabled pytest cache provider in `pytest.ini` (`-p no:cacheprovider`) to avoid local `pytest-cache-files-*` leftovers on this Windows workspace.

---
## v0.7.13 - 2026-06-28
### Baseline: source boundary decision
- Decided the current source baseline for `kaoyan-assistant` under the parent Git root `D:\AI\agent`.
- Treat application source, tests, scripts, deployment files, and long-term docs as the active baseline even when currently untracked by Git.
- Keep local learning data, vector DBs, secrets, virtual environments, frontend build/dependency outputs, logs, backups, and exports outside the source baseline per `.gitignore` and `docs/project_layout.md`.

### Feature: exercise practice loop MVP
- **Changed** `memory/exercise_bank.py`
  - Add practice fields: `last_practiced`, `practice_count`, and `practice_history`.
  - Add `record_practice()` to record user answer, quality score, note, and update status (`needs_review`, `practicing`, `mastered`).
- **Changed** `backend/schemas.py` and `backend/api/exercises.py`
  - Add `/api/exercises/practice` for recording a practice attempt.
  - Add `/api/exercises/to-mistake` for sending an exercise into the mistake book with the user's attempted answer.
  - Preserve `/api/exercises/from-mistake` for the reverse flow.
- **Changed** `frontend/src/pages/ExercisesPage.tsx`
  - Add a practice panel at the top of the exercise bank.
  - Prioritize `needs_review`, `practicing`, and `new` exercises.
  - Let the user write an answer, reveal answer/explanation, rate the attempt, and send a hard miss to the mistake book.
- **Changed** `frontend/src/types/index.ts`
  - Add practice metadata to the `ExerciseRecord` type.
- **Changed** `tests/test_exercise_bank.py`
  - Cover exercise practice history, API practice recording, and exercise-to-mistake conversion.

### Validation
- `python -B -c "import memory.exercise_bank, backend.schemas, backend.api.exercises"` passes.
- `python -m pytest -q` passes: 30 passed.
- `npm.cmd run build` passes; the existing large chunk warning remains.
- A direct `py_compile` run without `-B` hit a Windows `__pycache__` permission error, so import validation used bytecode-disabled mode.

---
## v0.7.14 - 2026-06-28
### Fix: learning summary loading latency
- **Changed** `backend/api/kg.py`
  - Removed per-request KG wiki enrichment from learning-summary review-card construction.
  - Concept review cards now use ConceptMemory definitions/source chapters and mistake context only, avoiding expensive repeated KG lookups.
- **Changed** `frontend/src/api/client.ts`
  - Added a 20-second timeout wrapper for normal GET/POST API calls so pages do not spin forever on stalled requests.
- **Changed** `frontend/src/pages/LearningPage.tsx`
  - Clarified the loading message for large learning summaries.

### UI: exercise bank cleanup
- **Changed** `frontend/src/pages/ExercisesPage.tsx`
  - Removed the manual single-exercise input panel from the visible UI.
  - Reorganized the page around Word/PDF import, candidate confirmation, practice, and the exercise list.
  - Reduced the left sidebar width and kept it focused on target selection plus file analysis.
  - Kept practice actions and exercise-to-mistake flow, but moved list/status management into a cleaner right-side layout.

### Validation
- Fresh TestClient call to `/api/kg/learning-summary?book_name=浼樺寲璁捐` returns successfully in about 0.06s with the optimized code.
- `python -m pytest -q` passes: 30 passed.
- `npm.cmd run build` passes; the existing large chunk warning remains.
- Browser smoke check confirms the exercise page no longer exposes manual add/save controls and has no console errors.

### Operational note
- The running backend process on port 8000 must be restarted before the learning-summary latency fix is visible in the browser.

---
## v0.7.15 - 2026-06-28
### Product decision: remove knowledge graph UI, keep concept system
- **Changed** `frontend/src/App.tsx`
  - Removed the active KnowledgeGraph page route and redirected `/kg` to `/learning`.
- **Changed** `frontend/src/layouts/MainLayout.tsx`
  - Removed the sidebar `鐭ヨ瘑鍥捐氨` navigation entry.
- **Changed** `frontend/src/components/ConceptPopover.tsx`
  - Renamed concept fallback wording from knowledge graph language to concept index language.
  - Removed display of inferred prerequisite/successor concept relations from the concept popover.
- **Changed** `frontend/src/components/SystemHealth.tsx`, `backend/api/system.py`, and `tests/test_system_health.py`
  - Removed knowledge graph from system health as a first-class component.
- **Changed** `backend/main.py`
  - Stopped warming the knowledge graph at backend startup.

### Kept
- ConceptMemory, concept extraction, concept review cards, and `/api/kg/learning-summary` / `/api/kg/concept-review` remain available for the learning workflow.
- Historical `/api/kg/*` route names are still present where the concept system depends on them; they can be renamed later without changing product behavior.

### Validation
- `python -m pytest -q` passes: 30 passed.
- `npm.cmd run build` passes; the existing large chunk warning remains.
- `backend.main` and `backend.api.system` import successfully.

### Note
- `frontend/src/pages/KnowledgeGraphPage.tsx` is no longer referenced and its contents were cleared, but Windows denied deleting the empty compressed file in this workspace.

---
## v0.7.16 - 2026-06-28
### UI/Workflow: learning page review clarity
- **Changed** `backend/api/kg.py`
  - Added subject-aware learning summary data for mistake stats, due mistakes, weak points, and concept review cards.
  - Added explicit review-rule text for due mistakes, concept review priority, and the meaning of marking a concept reviewed.
  - Returned due mistake summaries and expanded related mistakes for concept review cards, preserving question text for LaTeX rendering.
  - Reduced textbook clues in concept review cards to extracted chapter titles only.
  - Added best-effort mistake ids to recent mistake questions so the frontend can route back to the mistake book.
- **Changed** `frontend/src/pages/LearningPage.tsx`
  - Added a subject filter in the page header.
  - Added expandable sections for due mistakes, today's concept review, recent key questions, and due concepts.
  - Rendered recent questions and related mistakes through `ChatMessage` so LaTeX is displayed consistently.
  - Added links from related mistakes/recent mistake questions into the mistake book.
  - Added compact rule cards explaining how due mistakes, due concepts, and reviewed concepts are calculated.
- **Changed** `frontend/src/pages/MistakesPage.tsx`
  - Added support for `?mistake_id=...` deep links: the page switches to the list tab, loads the target record if needed, and expands it.

### Validation
- `python -B -c "import backend.api.kg"` passes.
- `python -m pytest -q` passes: 30 passed.
- `npm.cmd run build` passes; the existing large chunk warning remains.

---
## v0.7.17 - 2026-06-28
### UI: simplify learning review cards
- **Changed** `frontend/src/pages/LearningPage.tsx`
  - Removed the visible three-card review-rule row and moved the standards into a question-mark popover on the `浠婃棩寰呭涔犻敊棰榒 metric.
  - Removed the `鏈€杩戝叧閿棶棰榒 section from the learning page.
  - Simplified `浠婃棩姒傚康澶嶄範` details: concept cards no longer render mistake question content or recent question content inline.
  - Kept textbook clues as chapter-title text and changed related mistakes into lightweight links to the mistake book / specific mistake records.

### Validation
- `npm.cmd run build` passes; the existing large chunk warning remains.
- `python -m pytest -q` passes: 30 passed.

---
## v0.7.18 - 2026-06-28
### UI/Data: daily activity contribution calendar
- **Changed** `backend/api/kg.py`
  - Added `daily_details` to learning summary responses.
  - Daily details include per-date totals, QA/mistake counts, subject breakdowns, and top concepts for each subject.
  - Mistake-sourced concept exposures are grouped by the linked mistake subject when possible; single-subject books fall back to that subject, otherwise unresolved QA records are grouped as `鏈垎绫籤.
- **Changed** `frontend/src/pages/LearningPage.tsx`
  - Replaced the plain `鏈€杩戞瘡鏃ユ椿鍔╜ list with a GitHub-style green contribution calendar.
  - Clicking a day shows that day's QA/mistake counts, subject breakdown, and important concepts.
  - Kept the activity panel wider and moved high-frequency concepts / mistake weak points into the side column.

### Validation
- TestClient `/api/kg/learning-summary?book_name=浼樺寲璁捐` returns `daily_details` with date, subject, and concept data.
- `npm.cmd run build` passes; the existing large chunk warning remains.
- `python -m pytest -q` passes: 30 passed.

---
## v0.7.19 - 2026-06-28
### UI/Data: compact daily activity card
- **Changed** `frontend/src/pages/LearningPage.tsx`
  - Reduced `鏈€杩戞瘡鏃ユ椿鍔╜ from a wide activity panel to a compact card in the same three-column area as high-frequency concepts and mistake weak points.
  - Kept the contribution-calendar interaction, but moved selected-day details below the small calendar inside the same card.
  - Renamed the selected-day detail behavior from broad subject-style grouping to textbook/concept display.
- **Changed** `backend/api/kg.py`
  - Daily activity details now group concept activity under the current `book_name`, returning `book_name` alongside the existing compatibility field.
  - Removed the misleading fallback that displayed single-subject labels such as `鏁板` for textbook-specific concept activity.

### Validation
- TestClient `/api/kg/learning-summary?book_name=浼樺寲璁捐` returns daily details under `book_name: 浼樺寲璁捐`.
- `npm.cmd run build` passes; the existing large chunk warning remains.
- `python -m pytest -q` passes: 30 passed.

---
## v0.7.20 - 2026-06-28
### Architecture: external MinerU 3.x import service and study agent surfaces
- **Added** `ingestion/mineru_client.py`
  - Added a lightweight HTTP client for external MinerU 3.x async task APIs: `POST /tasks`, `GET /tasks/{id}`, and `GET /tasks/{id}/result`.
  - Kept MinerU/Paddle/CUDA/vLLM dependencies out of the main application environment.
- **Added** `ingestion/mineru_importer.py`
  - Added textbook import pipeline: MinerU output -> `content_list` / `middle` parsing -> chapters -> vector index rebuild.
  - Added MinerU output text extraction for reuse by exercise import.
- **Changed** `backend/api/books.py`
  - Replaced blocking textbook import with async import jobs via `/api/books/import-job` and `/api/books/import-jobs/{job_id}`.
  - Kept `/api/books/import-local` as an explicit local TOC-only fallback.
  - Persisted import job status under `data/progress/import_jobs`.
- **Changed** `frontend/src/pages/BooksPage.tsx`
  - Rebuilt textbook import UI around job progress stages: submit, MinerU running, download, structure, indexing, completed/failed.
- **Added** `backend/conversation_memory.py`
  - Added `conversation_id` persistence and follow-up rewriting based on recent dialogue context.
- **Changed** `backend/api/chat.py`, `backend/schemas.py`, `frontend/src/api/client.ts`, `frontend/src/hooks/useChat.ts`, `frontend/src/contexts/ChatContext.tsx`, `frontend/src/pages/ChatPage.tsx`
  - Chat requests now carry `subject` and `conversation_id`.
  - Chat page now has a subject selector, textbook selector, and new-conversation action.
- **Changed** `memory/exercise_file_importer.py`
  - PDF exercise import now prefers MinerU when `MINERU_API_URL` is configured, then feeds extracted text into the existing rule-based candidate splitter and confirmation workflow.
  - DOCX import continues to use direct Word XML extraction.
- **Added** `backend/api/reports.py`, `frontend/src/pages/WeeklyReportPage.tsx`
  - Added deterministic weekly report summary for QA count, mistakes, exercise practice, concept exposure, weak points, and next-week suggestions.
- **Changed** `docker-compose.yml`, `.env.example`, `docs/docker_deploy.md`, `docs/new_user_deploy.md`
  - Added `MINERU_OUTPUT_PATH`, `MINERU_TASK_TIMEOUT_SECONDS`, and `MINERU_TASK_POLL_SECONDS`.
  - Mounted `./mineru_output:/app/mineru_output` for main-app access to downloaded MinerU results.
- **Added** `docs/mineru_deploy.md`
  - Documented local MinerU service, rented-GPU SSH tunnel, app behavior, and fallbacks.

### Validation
- `python -m pytest -q` passes: 30 passed, 3 warnings.
- `npm.cmd run build` passes; the existing large chunk warning remains.
- Import smoke test passes for `backend.main`, `ingestion.mineru_client`, `ingestion.mineru_importer`, and `memory.exercise_file_importer`.
- FastAPI TestClient checks pass for `/api/books/list` and `/api/reports/weekly?book_name=default`.

### Notes
- MinerU runtime itself was not launched locally in this validation; `MINERU_API_URL` must point to a running MinerU 3.x API service, or `MINERU_CLI_COMMAND` must point to a local MinerU command template, before real scanned-PDF import can be verified end to end.
- The main Docker image intentionally does not install MinerU dependencies.`r`n- `MINERU_CLI_COMMAND` is a configurable fallback for local CLI execution; the default path remains the external API service.


---
## v0.7.21 - 2026-06-28
### UI: chat-scoped reports and subject textbook hierarchy
- **Changed** `frontend/src/pages/ChatPage.tsx`
  - Moved learning daily/weekly report access under the chat input as expandable options.
  - Reworked the chat header selectors into a clearer subject -> textbook hierarchy.
  - Filtered textbooks by subject using filename heuristics until textbook metadata has explicit subject fields.
- **Changed** `frontend/src/pages/WeeklyReportPage.tsx`
  - Extracted `LearningReportPanel` for reuse inside the chat page.
  - Reused the weekly report endpoint with `days=1` for the daily report view.
- **Changed** `frontend/src/layouts/MainLayout.tsx`, `frontend/src/index.css`
  - Removed the standalone weekly-report sidebar entry.
  - Added select styling for compact embedded selectors to avoid text/icon overlap.

### Validation
- `npm.cmd run build` passes; the existing large chunk warning remains.

---
## v0.7.22 - 2026-06-28
### UI: taste-skill guided frontend redesign
- **Changed** `frontend/src/index.css`
  - Recalibrated the visual system from warm beige/orange to a quieter grey-green study workspace palette.
  - Unified typography, form focus states, scrollbars, select controls, shadows, and reusable surface tokens.
- **Changed** `frontend/src/layouts/MainLayout.tsx`, `frontend/src/components/ChapterTree.tsx`, `frontend/src/components/SystemHealth.tsx`
  - Refined the app shell, textbook selector, chapter tree, navigation, and system health surfaces without changing routing or data flow.
  - Fixed mojibake display strings in the chapter tree empty state and skip keywords.
- **Changed** `frontend/src/pages/ChatPage.tsx`, `frontend/src/components/ChatMessage.tsx`
  - Refined the chat header, empty state, input tray, report toggles, and message rendering surfaces.
  - Kept the existing subject -> textbook selector logic, with automatic subject inference when the current sidebar textbook syncs into chat.
- **Changed** `frontend/src/pages/BooksPage.tsx`, `frontend/src/pages/LearningPage.tsx`, `frontend/src/pages/MistakesPage.tsx`, `frontend/src/pages/ExercisesPage.tsx`, `frontend/src/pages/WeeklyReportPage.tsx`
  - Updated major workflow pages to the new surface, spacing, radius, and accent system while preserving their existing interactions and API calls.

### Validation
- `npm.cmd run build` passes; the existing large chunk warning remains.
- Browser visual smoke checks passed for chat,教材导入,习题库, and错题本 at `http://127.0.0.1:5173/`.

---
## v0.7.23 - 2026-06-28
### UI/Build: chat-native reports and production chunk split
- **Changed** `frontend/vite.config.ts`
  - Added manual vendor chunking for React, Markdown/KaTeX, icons, and remaining dependencies.
  - Removed the Vite production large chunk warning without raising the warning threshold.
- **Changed** `frontend/src/types/index.ts`, `frontend/src/contexts/ChatContext.tsx`, `frontend/src/components/ChatMessage.tsx`
  - Added chat-native report card payload support.
  - Assistant messages can now render a compact learning report card with expandable full details.
- **Changed** `frontend/src/pages/ChatPage.tsx`
  - Learning daily/weekly buttons now append a user-like request and a deterministic assistant report card into the chat stream.
  - Report data is fetched directly from the existing `/api/reports/weekly` endpoint with `days=1` or `days=7`, without invoking the LLM.

### Validation
- `npm.cmd run build` passes with no large chunk warning.
- Browser smoke test confirms 学习日报 appears inside the chat stream as a compact card and expands to full details.

---
## v0.7.24 - 2026-06-28
### UI: chat quick actions for exercises and mistake capture
- **Changed** `frontend/src/types/index.ts`, `frontend/src/contexts/ChatContext.tsx`
  - Added chat payload types for exercise cards and utility cards.
- **Changed** `frontend/src/components/ChatMessage.tsx`
  - Added a chat-native random exercise card with question rendering, answer/explanation reveal, and practice result actions.
  - Added a chat-native quick mistake capture card with image upload, OCR, image solving, manual correction, metadata fields, and save-to-mistake-book action.
- **Changed** `frontend/src/pages/ChatPage.tsx`
  - Added `随机抽题` and `错题速录` quick action buttons below the chat input.
  - Random exercise selection prioritizes `needs_review`, then `practicing`, then `new`, then non-mastered fallback.

### Validation
- `npm.cmd run build` passes with no large chunk warning.
- Browser smoke test confirms `随机抽题` and `错题速录` buttons render; `错题速录` opens the OCR capture card; empty exercise bank degrades with a clear chat message.

## 2026-06-29 Electron 无边框桌面壳与优化设计示例包

- 新增 `desktop/` Electron 桌面壳：使用无边框窗口加载本地 FastAPI 服务，开发模式默认通过 `venv310` 启动 `uvicorn backend.main:app`，打包模式预期启动 `build/backend/backend_server/backend_server.exe`。
- 新增前端 Electron 标题栏组件，仅在 `window.kaoyanDesktop` 存在时显示，提供最小化、最大化/还原、关闭按钮；普通网页模式不显示。
- 新增 `desktop/backend_server.py` 和 `scripts/build-desktop-backend.ps1`，用于先构建前端 dist，再用 PyInstaller 构建桌面壳可调用的后端 exe。
- 新增 `scripts/export-optimization-demo-package.ps1`，默认导出“优化设计”的 progress、错题库、习题库和 Chroma 向量库，默认不包含原始 PDF、API Key、虚拟环境或日志。
- 已生成示例包：`exports/kaoyan-assistant-demo-优化设计-20260629_103135.zip`。
- 验证：已运行 `npm.cmd run build`，前端 TypeScript 与 Vite 生产构建通过。

## 2026-06-29 Electron 标题栏视觉修正

- 将 Electron 无边框标题栏改为右上角胶囊式窗口控制区，只保留最大化/还原与关闭按钮。
- 移除标题栏中的裸露应用名称和最小化按钮，顶部保留可拖拽区域。
- 修复标题栏 CSS 未生效导致页面被普通 DOM 撑高的问题；Electron 模式下主布局高度改为 `calc(100dvh - 44px)`，避免正常窗口尺寸下内容溢出。
- 验证：已运行 `npm.cmd run build`，前端生产构建通过。

## 2026-06-29 错题速录聊天卡片流程调整

- 聊天页“错题速录”新增 OCR 题干 LaTeX 预览，保留 textarea 供手动校对，解决公式只显示原始 LaTeX 的问题。
- “保存到错题本”改为仅在“看图解题”完成并拿到解答后显示；未解题时无法保存。
- 解题完成后不再把完整讲解展开挤在聊天界面，只显示完成提示；保存后自动跳转到错题本页面并展开对应错题记录。
- 验证：已运行 `npm.cmd run build`，前端生产构建通过。

## 2026-06-29 主标题精简、健康检查入口与学习情况超时修复

- 移除主标题下方的副标题文案，包括左侧 `Study Workspace`、学习情况页教材名、对话页说明、教材导入说明、习题库说明和周报说明，减少 AI 模板感。
- 将系统健康检查从侧边栏独立状态卡改为“考研助手”标题旁的小扳手入口，点击后弹出各组件检查状态并可手动刷新。
- `api/client.ts` 的 `get/post` 支持自定义超时；学习情况页请求超时放宽到 90 秒，避免数据较多时触发 `signal is aborted without reason`。
- 学习情况页学科筛选不再因空列表长期禁用，加载完成后会使用后端返回的学科列表填充。
- 验证：已运行 `npm.cmd run build`，前端生产构建通过。

## 2026-06-29 教材与自定义学科解耦

- 新增 `SubjectInput` 可自定义学科输入组件，提供常见学科建议，同时允许输入线代、微积分、概率论等自定义科目。
- 对话页将“科目”和“教材”解耦：教材可不选，学科可自定义；选择教材不再强制覆盖学科。
- 聊天页错题速录新增学科输入，解题与保存错题时使用该自定义学科。
- 错题本录入的学科字段改为可建议输入；错题列表增加学科筛选，可输入自定义学科名过滤。
- 习题库导入目标改为“教材 / 学科”：有教材时优先选择教材，没有教材时可输入自定义学科名归档。
- 验证：已运行 `npm.cmd run build`，前端生产构建通过。

## 2026-06-29 设置中心、模型配置与统一学科管理

- 将“考研助手”旁的扳手入口升级为完整设置中心，包含服务器健康、版本更新、学科管理、模型配置四个面板。
- 新增后端 `/api/system/settings`、`/api/system/settings/env`、`/api/system/settings/subjects`、`/api/system/version`、`/api/system/update` 接口；模型配置写入本机 `.env`，API Key 只返回是否已配置，不在前后端明文回显。
- 新增统一学科树配置，默认示例包含数学/英语/政治/专业课及二级科目；保存到 `data/progress/subjects.json`，支持新增、编辑、删除一级学科和二级科目。
- `SubjectInput` 改为读取统一学科管理中的一二级科目，并继续允许用户直接输入自定义学科名。
- 错题图片 OCR 改为运行时读取 Moonshot/Kimi 环境变量，设置界面保存新 Key 后后续 OCR 请求可使用新配置。
- 修复 `backend/api/mistakes.py` 中遗留乱码提示导致的字符串断裂，并替换为正常中文提示。
- 验证：已运行后端接口导入检查；已运行 `npm.cmd run build`，前端生产构建通过。

## 2026-06-29 桌面版 GitHub Releases 自动更新通道

- 桌面壳接入 `electron-updater`，主进程新增检查更新、下载更新、重启安装 IPC 能力。
- `preload.cjs` 暴露 `getUpdateStatus`、`checkForUpdates`、`downloadUpdate`、`installUpdate` 和更新状态监听接口给前端。
- 设置中心“版本更新”页改为桌面版优先使用 Electron 自动更新；网页模式仍保留后端占位更新提示。
- 新增 `desktop/update-config.json`，用于配置 GitHub Releases 更新源；GitHub Actions 发版时会自动写入当前仓库 owner/repo。
- 新增 `.github/workflows/desktop-release.yml`，推送 `v*` tag 后自动构建 Windows 桌面安装包并发布到 GitHub Releases。
- 新增 `docs/desktop-auto-update.md`，记录版本号、tag、Release 和用户侧更新流程。
- `electron-updater` 移入 `desktop/package.json` 的 runtime dependencies；保留用户数据不随卸载/更新删除。
- 验证：已运行 `node --check desktop/main.cjs`；已运行 `npm.cmd run build`，前端生产构建通过。

## 2026-06-29 对话历史侧边栏与会话恢复

- 新增后端 `/api/chat/conversations` 和 `/api/chat/conversations/{conversation_id}`，基于 `data/progress/conversations` 中的会话文件返回历史列表与详情。
- 扩展会话持久化元数据，记录 `subject`、`book_name`、`created_at`、`updated_at`，历史标题默认取首条用户问题。
- 对话页新增可展开/收起的左侧侧边栏，上方集中放置“科目 > 教材”范围选择，下方展示历史记录。
- 学科为空时视为“全部学科”，历史记录按每条会话所属学科显示柔和渐隐色条，透明度约 50%，用于区分但不抢视觉焦点。
- 点击历史记录可恢复对应会话消息，并同步切换该会话的学科与教材范围。
- `ChatContext` 新增 `loadConversation`，支持从历史详情恢复消息、会话 id 和范围元数据。
- 验证：已运行后端导入检查；已运行 `npm.cmd run build`，前端生产构建通过。

## 2026-06-29 桌面版首次启动资源下载引导

- 新增后端 `/api/system/assets/status`、`/api/system/assets/download/embedding`、`/api/system/assets/download/vector-bundle` 接口。
- 嵌入模型下载默认使用 `HF_ENDPOINT=https://hf-mirror.com`，模型版本由 `EMBEDDING_MODEL_NAME` 与 `EMBEDDING_MODEL_REVISION` 固定，下载完成后写入 `data/desktop_assets.json`。
- 示例向量库改为可配置下载包：通过 `KAOYAN_VECTOR_BUNDLE_URL`、`KAOYAN_VECTOR_BUNDLE_SHA256`、`KAOYAN_VECTOR_BUNDLE_VERSION` 控制来源、校验和版本；下载时先校验再解压到运行时 `VECTOR_DB_PATH`。
- 新增前端 `FirstRunGuide` 首次启动引导，资源缺失时提示用户下载嵌入模型和示例向量库；用户可稍后跳过，资源保存到用户数据目录，不随安装包更新覆盖。
- 桌面 PyInstaller 构建脚本补充 `huggingface_hub` hidden import，并继续排除 PaddleOCR、Gradio、Ultralytics 等非核心重依赖。
- 验证：已运行后端 AST 检查、`import backend.main` 检查；已运行 `npm.cmd run build`，前端生产构建通过。

## 2026-06-29 首次启动教程与 API Key 泄漏审查

- 首次启动引导扩展为“快速了解 / 本地资源 / 模型配置”三步：先说明对话、教材导入、错题本和设置入口，再引导用户确认本地嵌入模型、示例向量库和 API Key 配置。
- 首启模型配置页可录入 DeepSeek 与 Kimi/OCR Key；已有 Key 只显示“已配置/未配置”，输入框不回显旧密钥，保存后仍写入本机 `.env`，后续仍可在设置中心管理。
- 设置中心模型配置继续保留 DeepSeek、Kimi/OCR、OpenAI 等配置入口，修复侧边栏出现两个设置按钮的问题。
- 安全审查发现并修复一类风险：如果非密钥环境变量中误混入 `sk-...`，资源状态接口可能把该字符串作为模型名展示。现已对公开返回值做脱敏/校验，`EMBEDDING_MODEL_NAME` 也限制为合法 `owner/repo` 形式，否则回退到 `BAAI/bge-small-zh-v1.5`。
- 后端 `/api/system/settings` 对 API Key 只返回 configured 状态和空 value；`/api/system/assets/status` 返回的 repo、revision、HF endpoint 均经过公开字段净化。
- 后端启动默认跳过嵌入模型 warmup，避免未下载本地模型时首启卡住；桌面壳和打包后端也设置 `SKIP_EMBEDDING_WARMUP=1`。
- 验证：已运行后端 AST 与 `import backend.main` 检查；已运行 `npm.cmd run build`；已检查设置接口、资源状态接口和主要前端页面，均未发现 `sk-...` 形态密钥回显；已截图验证首启三步引导、设置中心和主要页面导航。
## 2026-06-29 桌面安装包重打包

- 已重新运行 `scripts/build-desktop-backend.ps1`，完成前端生产构建与 PyInstaller 后端 exe 构建。
- 已运行 `desktop` 目录下的 `npm.cmd run dist`，生成 Windows NSIS 安装包 `release/kaoyan-assistant-desktop-setup-0.1.0.exe`。
- 安装包文件名改为 ASCII，避免 GitHub Releases / `latest.yml` 自动更新元数据在中文文件名下出现编码不一致；应用显示名和桌面快捷方式仍为“考研智能辅助系统”。
- 修复 `desktop/main.cjs` 中桌面主进程更新状态、窗口标题、启动错误等中文文案乱码问题，并通过 `node --check desktop/main.cjs`。
- 验证：`latest.yml` 指向新安装包；打包资源中未发现 `.env`、`*.env` 或 `*.key`；已用打包后的 `backend_server.exe` 在临时端口启动并访问 `/api/system/settings`，确认接口成功且未回显 `sk-...` 形态密钥。
- 产物大小：Setup 约 1847.22 MB，`win-unpacked` 约 3314.04 MB，其中后端资源约 2994.60 MB。