#!/bin/sh
set -eu

mkdir -p \
  "${DATA_DIR:-/app/data}" \
  "${BOOKS_PATH:-/app/data/books}" \
  "${CHAPTERS_PATH:-/app/data/chapters}" \
  "${PROGRESS_PATH:-/app/data/progress}" \
  "${IMAGES_PATH:-/app/data/images}" \
  "${VECTOR_DB_PATH:-/app/data/vector_db}" \
  "${DATA_DIR:-/app/data}/models" \
  "${DATA_DIR:-/app/data}/logs"

exec python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
