"""向量存储模块 - 为每个章节创建独立的向量数据库"""
import json, time
from pathlib import Path
from langchain_chroma import Chroma
from langchain_core.documents import Document

from config import VECTOR_DB_PATH, get_embeddings

# ── 全局单例缓存 ──────────────────────────────────────────
_chapter_vs_instance = None


def get_vector_store() -> "ChapterVectorStore":
    """获取全局 ChapterVectorStore 单例实例（避免每次请求重复初始化）"""
    global _chapter_vs_instance
    if _chapter_vs_instance is None:
        _chapter_vs_instance = ChapterVectorStore()
    return _chapter_vs_instance


class ChapterVectorStore:
    """每个章节独立的向量存储管理器"""

    def __init__(self):
        print("  [向量库] 初始化中...", flush=True)
        self.embeddings = get_embeddings()
        self.db_path = Path(VECTOR_DB_PATH)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self._stores: dict[str, Chroma] = {}
        self._map_file = self.db_path / "_chapter_map.json"
        self._map: dict[str, str] = self._load_map()
        self.available = True
        # Recover mapping from existing collection metadata when Chroma is healthy.
        try:
            self._recover_map_from_collections()
        except Exception as e:
            self.available = False
            print(f"  [vector_store] Chroma unavailable, retrieval will degrade: {e}", flush=True)
        # Preload only when Chroma can be opened successfully.
        if self.available:
            self._preload_all_stores()
        print("  [向量库] 就绪（已缓存，后续请求复用）", flush=True)

    def _preload_all_stores(self):
        """启动时预加载所有章节的 Chroma 实例，避免冷启动延迟。"""
        import chromadb
        try:
            client = chromadb.PersistentClient(path=str(self.db_path))
            cols = [c for c in client.list_collections() if c.name != "_chapter_map.json"]
            for col in cols:
                title = self._collection_to_title(col.name)
                if title not in self._stores:
                    try:
                        store = Chroma(
                            collection_name=col.name,
                            embedding_function=self.embeddings,
                            persist_directory=str(self.db_path),
                        )
                        self._stores[title] = store
                    except Exception:
                        pass
            if self._stores:
                print(f"  [向量库] 预加载 {len(self._stores)} 个章节存储", flush=True)
        except Exception:
            pass

    # === 章节名 ↔ collection 名 映射 ===

    def _load_map(self) -> dict[str, str]:
        """加载映射: {collection_name: chapter_title}"""
        if self._map_file.exists():
            with open(self._map_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_map(self):
        with open(self._map_file, "w", encoding="utf-8") as f:
            json.dump(self._map, f, ensure_ascii=False, indent=2)

    def _recover_map_from_collections(self):
        """从已有 collection 的 metadata 恢复章节标题映射"""
        import chromadb
        client = chromadb.PersistentClient(path=str(self.db_path))
        for col in client.list_collections():
            if col.name in self._map or col.name == "_chapter_map.json":
                continue
            try:
                peek = col.peek(limit=1)
                metas = peek.get("metadatas", []) if peek else []
                if metas and metas[0]:
                    title = metas[0].get("chapter", "")
                    if title:
                        self._map[col.name] = title
            except Exception:
                pass
        if self._map:
            self._save_map()

    def _chapter_collection_name(self, chapter_title: str) -> str:
        """为章节生成合法的 collection 名"""
        import hashlib
        safe = "".join(c if c.isascii() and c.isalnum() or c in "_-" else "" for c in chapter_title)
        if len(safe) >= 3 and safe[0].isalnum() and safe[-1].isalnum():
            return safe[:63]
        h = hashlib.md5(chapter_title.encode()).hexdigest()[:16]
        return f"ch{h}"

    def _collection_to_title(self, collection_name: str) -> str:
        """collection 名 -> 中文标题"""
        return self._map.get(collection_name, collection_name)

    def _title_to_collection(self, chapter_title: str) -> str:
        """中文标题 -> collection 名（反向查）"""
        for col, title in self._map.items():
            if title == chapter_title:
                return col
        # 未命中：按旧规则计算
        return self._chapter_collection_name(chapter_title)

    # === 核心 API ===

    def build_chapter_store(self, chapter_title: str, chunks: list[dict],
                             chunk_roles: dict[str, str] | None = None):
        """为单个章节创建向量存储

        Args:
            chunk_roles: {chunk_id: role} 映射，用于写入 metadata
        """
        collection_name = self._chapter_collection_name(chapter_title)
        chunk_roles = chunk_roles or {}

        documents = [
            Document(
                page_content=chunk["content"],
                metadata={
                    "chapter": chunk.get("chapter", chapter_title),
                    "chunk_index": chunk.get("chunk_index", 0),
                    "chunk_id": chunk.get("chunk_id", ""),
                    "role": chunk_roles.get(chunk.get("chunk_id", ""), "reference"),
                },
            )
            for chunk in chunks
        ]

        store = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            collection_name=collection_name,
            persist_directory=str(self.db_path),
        )
        self._stores[chapter_title] = store
        # 保存映射
        self._map[collection_name] = chapter_title
        self._save_map()
        return store

    def get_chapter_store(self, chapter_title: str) -> Chroma | None:
        """获取章节的向量存储（支持中文标题或 collection 名）"""
        if not self.available:
            return None
        if chapter_title in self._stores:
            return self._stores[chapter_title]

        # 先尝试作为中文标题查找
        collection_name = self._title_to_collection(chapter_title)
        try:
            store = Chroma(
                collection_name=collection_name,
                embedding_function=self.embeddings,
                persist_directory=str(self.db_path),
            )
            self._stores[chapter_title] = store
            return store
        except Exception:
            return None

    def get_chapter_names(self) -> list[str]:
        """获取所有已索引的章节名（返回中文标题）"""
        if not self.available:
            return list(self._map.values())
        import chromadb
        try:
            client = chromadb.PersistentClient(path=str(self.db_path))
            collections = client.list_collections()
        except Exception as e:
            self.available = False
            print(f"  [vector_store] list_collections failed, using chapter map only: {e}", flush=True)
            return list(self._map.values())
        names = []
        for col in collections:
            if col.name == "_chapter_map.json":
                continue
            names.append(self._collection_to_title(col.name))
        return names

    def search_chapter(self, chapter_title: str, query: str, k: int = 5,
                        filter: dict | None = None) -> list[Document]:
        """在指定章节中检索相关内容

        Args:
            filter: ChromaDB where 过滤条件，如 {"role": {"$eq": "definition"}}
        """
        store = self.get_chapter_store(chapter_title)
        if store is None:
            return []
        kwargs = {"k": k}
        if filter:
            kwargs["filter"] = filter
        try:
            return store.similarity_search(query, **kwargs)
        except Exception as e:
            # Chroma may keep a collection record whose HNSW segment is missing
            # after an interrupted rebuild. Skip it so callers can fall back.
            self._stores.pop(chapter_title, None)
            print(f"  [向量库] 章节检索失败，已跳过 {chapter_title}: {e}", flush=True)
            return []

    def search_all(self, query: str, k: int = 3, top_n: int = 3,
                   filter: dict | None = None) -> dict[str, list[Document]]:
        """在所有章节中检索（query 只 embed 一次，按相似度排序，只返回最相关的 top_n 章）

        Args:
            filter: ChromaDB where 过滤条件，如 {"role": {"$eq": "definition"}}
        """
        if not self.available:
            return {}
        t0 = time.time()
        # 1. query 只 embed 一次
        query_vec = self.embeddings.embed_query(query)
        dt_embed = time.time() - t0

        # 2. 复用已有 store 实例，by_vector 搜索（带分数排序）
        scored_results: list[tuple[str, list[Document], float]] = []
        import chromadb
        try:
            client = chromadb.PersistentClient(path=str(self.db_path))
            collections = client.list_collections()
        except Exception as e:
            self.available = False
            print(f"  [vector_store] search_all skipped because Chroma is unavailable: {e}", flush=True)
            return {}
        searched = 0
        for col in collections:
            if col.name == "_chapter_map.json":
                continue
            title = self._collection_to_title(col.name)
            try:
                store = self._stores.get(title)
                if store is None:
                    store = Chroma(
                        collection_name=col.name,
                        embedding_function=self.embeddings,
                        persist_directory=str(self.db_path),
                    )
                    self._stores[title] = store
                # 尝试带分数的向量搜索，按相似度排序
                try:
                    kwargs = {"k": k}
                    if filter:
                        kwargs["filter"] = filter
                    docs_with_scores = store.similarity_search_by_vector_with_relevance_scores(query_vec, **kwargs)
                except Exception:
                    kwargs = {"k": k}
                    if filter:
                        kwargs["filter"] = filter
                    docs = store.similarity_search_by_vector(query_vec, **kwargs)
                    docs_with_scores = [(d, 1.0) for d in docs]
                if docs_with_scores:
                    docs = [d for d, s in docs_with_scores]
                    best_score = min(s for d, s in docs_with_scores)
                    scored_results.append((title, docs, best_score))
                searched += 1
            except Exception:
                pass

        # 3. 按相似度分数排序（距离越低越相似），只取 top_n 章
        scored_results.sort(key=lambda x: x[2])
        top_results = scored_results[:top_n]
        results = {title: docs for title, docs, score in top_results}

        dt_total = time.time() - t0
        print(f"  [检索] embed={dt_embed:.2f}s total={dt_total:.2f}s ({searched}章→取top{len(top_results)})", flush=True)
        return results
