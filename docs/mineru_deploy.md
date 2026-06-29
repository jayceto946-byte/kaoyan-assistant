# MinerU deployment

MinerU is treated as an external parsing service. The main `kaoyan-assistant` image does not install MinerU, Paddle, CUDA, PyTorch, or vLLM dependencies.

## Why separate it

- The main app must run on weak local machines and CPU-only Docker hosts.
- MinerU 3.x has heavier OCR/VLM/GPU dependencies and should be isolated.
- Rented GPU machines can run MinerU remotely while the local app only uploads PDFs and polls jobs.

## Main app settings

Configure these in `.env`:

```env
MINERU_API_URL=http://host.docker.internal:9001
MINERU_OUTPUT_PATH=./mineru_output
MINERU_TASK_TIMEOUT_SECONDS=3600
MINERU_TASK_POLL_SECONDS=2
# Optional CLI fallback when no API service is available.
# MINERU_CLI_COMMAND=mineru -p "{input}" -o "{output}" -m auto
```

Inside Docker Compose, `MINERU_OUTPUT_PATH` is mounted as `/app/mineru_output` and persisted on the host at `./mineru_output`.

## Local MinerU service

Use the official MinerU 3.x Docker/API deployment. The service must expose the async task API used by the app:

- `POST /tasks`
- `GET /tasks/{task_id}`
- `GET /tasks/{task_id}/result`

Then set:

```env
MINERU_API_URL=http://host.docker.internal:9001
```

If the main app runs outside Docker, use:

```env
MINERU_API_URL=http://127.0.0.1:9001
```

## Rented GPU service

Run MinerU on the rented GPU host and bind it to localhost on that host, for example `127.0.0.1:8000`. Then create an SSH tunnel from the local machine:

```powershell
ssh -L 9001:127.0.0.1:8000 user@gpu-server
```

Local `.env`:

```env
MINERU_API_URL=http://127.0.0.1:9001
```

This keeps the MinerU port private and avoids exposing the parsing service directly to the internet.

## CLI fallback

If a MinerU API service is unavailable but MinerU is installed on the same machine, set `MINERU_CLI_COMMAND` as a command template. The app replaces `{input}`, `{output}`, and `{book}` before execution. The command must write MinerU JSON/Markdown outputs under `{output}`.

Example:

```env
MINERU_CLI_COMMAND=mineru -p "{input}" -o "{output}" -m auto
```

Keep this unset when using the remote API service.

## App behavior

Textbook import now uses an async job:

1. Frontend uploads PDF to `/api/books/import-job`.
2. Backend saves the PDF under `data/books`.
3. Backend submits it to MinerU using `MINERU_API_URL`, or runs `MINERU_CLI_COMMAND` when configured.
4. Frontend polls `/api/books/import-jobs/{job_id}`.
5. Backend downloads or reads MinerU output into `mineru_output/<book>/hybrid_auto`.
6. Backend extracts chapters/text chunks and rebuilds vector indexes.

Exercise PDF import also prefers MinerU when `MINERU_API_URL` is configured. DOCX import still uses direct Word XML extraction.

## Fallbacks

- If neither `MINERU_API_URL` nor `MINERU_CLI_COMMAND` is configured and textbook import requires MinerU, the job fails clearly.
- `/api/books/import-local` remains available for local TOC-only parsing.
- If exercise PDF MinerU parsing fails, the importer falls back to the PDF text layer and returns warnings.
