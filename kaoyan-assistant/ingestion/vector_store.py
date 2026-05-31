"""向量存储模块 - 为每个章节创建独立的向量数据库"""
from pathlib import Path
from langchain_chroma import Chroma
from langchain_core.documents import Document

from config import VECTOR_DB_PATH, get_embeddings


class ChapterVectorStore:
    """每个章节独立的向量存储管理器"""

    def __init__(self):
        self.embeddings = get_embeddings()
        self.db_path = Path(VECTOR_DB_PATH)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self._stores: dict[str, Chroma] = {}

    def _chapter_collection_name(self, chapter_title: str) -> str:
        """为章节生成合法的collection名"""
        name = "".join(c if c.isalnum() or c in "-_" else "_" for c in chapter_title)
        # Chroma collection name max length
        return name[:63]

    def build_chapter_store(self, chapter_title: str, chunks: list[dict]):
        """为单个章节创建向量存储
        
        Args:
            chapter_title: 章节标题
            chunks: 包含 'content' 和 'chapter' 键的块列表
        """
        collection_name = self._chapter_collection_name(chapter_title)

        documents = [
            Document(
                page_content=chunk["content"],
                metadata={
                    "chapter": chunk.get("chapter", chapter_title),
                    "chunk_index": chunk.get("chunk_index", 0),
                    "chunk_id": chunk.get("chunk_id", ""),
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
        return store

    def get_chapter_store(self, chapter_title: str) -> Chroma | None:
        """获取章节的向量存储"""
        if chapter_title in self._stores:
            return self._stores[chapter_title]

        collection_name = self._chapter_collection_name(chapter_title)
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
        """获取所有已索引的章节名"""
        import chromadb
        client = chromadb.PersistentClient(path=str(self.db_path))
        collections = client.list_collections()
        return [col.name for col in collections]

    def search_chapter(self, chapter_title: str, query: str, k: int = 5) -> list[Document]:
        """在指定章节中检索相关内容"""
        store = self.get_chapter_store(chapter_title)
        if store is None:
            return []
        return store.similarity_search(query, k=k)

    def search_all(self, query: str, k: int = 3) -> dict[str, list[Document]]:
        """在所有章节中检索"""
        results = {}
        for ch_name in self.get_chapter_names():
            docs = self.search_chapter(ch_name, query, k=k)
            if docs:
                results[ch_name] = docs
        return results
