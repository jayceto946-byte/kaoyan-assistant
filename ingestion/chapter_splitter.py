"""章节分割器 - 将提取的章节文本切分为适合embedding的块"""
import json
import hashlib
from pathlib import Path


def _get_splitter(chunk_size: int, chunk_overlap: int):
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", "；", "，", " ", ""],
        )
    except ImportError:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", "；", "，", " ", ""],
        )


class ChapterSplitter:
    """章节文本分割器"""

    def __init__(self, chunk_size: int = 2000, chunk_overlap: int = 100):
        self.splitter = _get_splitter(chunk_size, chunk_overlap)

    def split_chapter(self, title: str, text: str) -> list[dict]:
        """将单个章节切分为块
        
        Returns:
            [{"chapter": title, "chunk_index": i, "content": text}, ...]
        """
        chunks = self.splitter.split_text(text)
        return [
            {
                "chapter": title,
                "chunk_index": idx,
                "content": chunk,
                "chunk_id": hashlib.md5(f"{title}_{idx}".encode()).hexdigest()[:12],
            }
            for idx, chunk in enumerate(chunks)
        ]

    def split_book(self, chapters: list[dict]) -> list[dict]:
        """将整本书的所有章节切分"""
        all_chunks = []
        for ch in chapters:
            chunks = self.split_chapter(ch["title"], ch["text"])
            all_chunks.extend(chunks)
        return all_chunks

    def save_chunks(self, chunks: list[dict], output_dir: str | Path):
        """保存分割后的块到文件"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 按章节分组保存
        by_chapter = {}
        for chunk in chunks:
            ch_name = chunk["chapter"]
            if ch_name not in by_chapter:
                by_chapter[ch_name] = []
            by_chapter[ch_name].append(chunk)

        for ch_name, ch_chunks in by_chapter.items():
            safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in ch_name)
            filepath = output_dir / f"{safe_name}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(ch_chunks, f, ensure_ascii=False, indent=2)

        # 保存完整索引
        with open(output_dir / "_all_chunks.json", "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)

        return len(chunks)
