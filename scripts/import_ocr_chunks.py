from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

ROOT = Path(r'D:\AI\agent\kaoyan-assistant')
DATA = ROOT / 'data'
DELIVERABLES = DATA / 'imports' / 'kaoyan_ocr_20260704' / 'deliverables'
VECTOR_DB = Path(r'C:\tmp\chroma_smoke_test')
PROGRESS = DATA / 'progress'
MODEL_SNAPSHOTS = DATA / 'models' / 'models--BAAI--bge-small-zh-v1.5' / 'snapshots'

BOOKS = {
    'sensor_core': {'book_name': '传感器短书', 'subject': '传感器', 'book_role': 'core', 'rag_priority': 1.0},
    'sensor_reference': {'book_name': '传感器长书', 'subject': '传感器', 'book_role': 'reference', 'rag_priority': 0.55},
    'error_theory': {'book_name': '误差理论与数据处理', 'subject': '误差理论与数据处理', 'book_role': 'core', 'rag_priority': 1.0},
}


def safe_name(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', '_', str(value)).strip(' ._')
    return value or 'book'


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def collection_name(book_name: str, title: str) -> str:
    h = hashlib.md5(f'{safe_name(book_name)}\0{title}'.encode('utf-8')).hexdigest()[:24]
    return f'bk{h}'

def book_collection_name(book_name: str) -> str:
    h = hashlib.md5(safe_name(book_name).encode('utf-8')).hexdigest()[:24]
    return f'book{h}'


def role(value) -> str:
    value = str(value or 'reference').strip()
    if value == 'formula':
        return 'derivation'
    if value == 'text':
        return 'reference'
    return value or 'reference'


def rows(path: Path):
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def grouped_chunks(book_id: str, meta: dict):
    grouped = defaultdict(list)
    for idx, row in enumerate(rows(DELIVERABLES / f'{book_id}_chunks.jsonl')):
        text = str(row.get('text') or '').strip()
        if not text:
            continue
        title = re.sub(r'\s+', ' ', str(row.get('title') or '')).strip() or f"{meta['book_name']} (全文)"
        chunk = {
            'content': text,
            'chunk_id': str(row.get('chunk_id') or f'{book_id}_{idx}'),
            'chapter': title[:120],
            'section_title': title[:120],
            'chunk_index': idx,
            'page_idx': int(row.get('page_idx', -1) or -1),
            'role': role(row.get('semantic_role')),
            'subject': str(row.get('subject') or meta['subject']),
            'book_role': str(row.get('book_role') or meta['book_role']),
            'rag_priority': float(row.get('rag_priority') or meta['rag_priority']),
            'review_status': str(row.get('review_status') or 'machine_generated'),
            'source_markdown': str(row.get('source_markdown') or ''),
        }
        grouped[chunk['chapter']].append(chunk)
    return dict(grouped)


print('[chroma]', VECTOR_DB)
client = chromadb.PersistentClient(path=str(VECTOR_DB))
map_file = VECTOR_DB / '_chapter_map.json'
try:
    chapter_map = json.loads(map_file.read_text(encoding='utf-8')) if map_file.exists() else {}
except Exception:
    chapter_map = {}

snapshots = list(MODEL_SNAPSHOTS.iterdir()) if MODEL_SNAPSHOTS.exists() else []
model_path = str(snapshots[0]) if snapshots else 'BAAI/bge-small-zh-v1.5'
print('[embedding]', model_path)
model = SentenceTransformer(model_path, device='cpu', cache_folder=str(DATA / 'models'), local_files_only=bool(snapshots))

def embed(texts):
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()

def add_aggregate_collection(book_id: str, meta: dict, grouped: dict):
    col_name = book_collection_name(meta['book_name'])
    try:
        client.delete_collection(col_name)
    except Exception:
        pass
    col = client.get_or_create_collection(col_name)
    all_chunks = [chunk for chunks in grouped.values() for chunk in chunks]
    for start in range(0, len(all_chunks), 64):
        batch = all_chunks[start:start + 64]
        texts = [c['content'] for c in batch]
        metadatas = [{
            'chapter': c['chapter'],
            'book_name': safe_name(meta['book_name']),
            'chunk_index': c['chunk_index'],
            'chunk_id': c['chunk_id'],
            'section_title': c['section_title'],
            'page_idx': c['page_idx'],
            'role': c['role'],
            'subject': c['subject'],
            'book_role': c['book_role'],
            'rag_priority': c['rag_priority'],
            'review_status': c['review_status'],
            'source_markdown': c['source_markdown'],
            'collection_schema': 2,
        } for c in batch]
        ids = [f"agg_{book_id}_{c['chunk_id']}_{start + i}" for i, c in enumerate(batch)]
        col.add(ids=ids, documents=texts, embeddings=embed(texts), metadatas=metadatas)
    chapter_map[col_name] = {
        'chapter': f"{meta['book_name']} (aggregate)",
        'book_name': safe_name(meta['book_name']),
        'schema_version': '2',
        'kind': 'book_aggregate',
    }
    print(f"[aggregate] {meta['book_name']}: {len(all_chunks)} chunks -> {col_name}")

summaries = []
for book_id, meta in BOOKS.items():
    grouped = grouped_chunks(book_id, meta)
    total = 0
    for title, chunks in grouped.items():
        col_name = collection_name(meta['book_name'], title)
        try:
            client.delete_collection(col_name)
        except Exception:
            pass
        col = client.get_or_create_collection(col_name)
        for start in range(0, len(chunks), 64):
            batch = chunks[start:start + 64]
            texts = [c['content'] for c in batch]
            metadatas = [{
                'chapter': c['chapter'],
                'book_name': safe_name(meta['book_name']),
                'chunk_index': c['chunk_index'],
                'chunk_id': c['chunk_id'],
                'section_title': c['section_title'],
                'page_idx': c['page_idx'],
                'role': c['role'],
                'subject': c['subject'],
                'book_role': c['book_role'],
                'rag_priority': c['rag_priority'],
                'review_status': c['review_status'],
                'source_markdown': c['source_markdown'],
                'collection_schema': 2,
            } for c in batch]
            ids = [f"{c['chunk_id']}_{start + i}" for i, c in enumerate(batch)]
            col.add(ids=ids, documents=texts, embeddings=embed(texts), metadatas=metadatas)
        chapter_map[col_name] = {'chapter': title, 'book_name': safe_name(meta['book_name']), 'schema_version': '2'}
        total += len(chunks)
        print(f"[index] {meta['book_name']} / {title}: {len(chunks)}")
    add_aggregate_collection(book_id, meta, grouped)
    write_json(PROGRESS / safe_name(meta['book_name']) / '_chapters.json', [
        {'title': title, 'page_number': 1, 'end_page': None, 'text': '\n\n'.join(c['content'] for c in chunks), 'source': 'external_ocr_jsonl', 'chunk_count': len(chunks)}
        for title, chunks in grouped.items()
    ])
    write_json(PROGRESS / safe_name(meta['book_name']) / 'metadata.json', {'subject': meta['subject'], 'import_source': 'external_ocr_jsonl', 'book_role': meta['book_role']})
    summaries.append({'book_id': book_id, 'book_name': meta['book_name'], 'chapters': len(grouped), 'chunks': total})

write_json(map_file, chapter_map)
print(json.dumps({'success': True, 'vector_db_path': str(VECTOR_DB), 'books': summaries}, ensure_ascii=False, indent=2))