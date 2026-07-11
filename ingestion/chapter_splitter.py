"""章节分割器 - 将提取的章节文本切分为适合embedding的块"""
import json
import hashlib
import re
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

    def __init__(self, chunk_size: int = 700, chunk_overlap: int = 80):
        self.splitter = _get_splitter(chunk_size, chunk_overlap)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_chapter(self, title: str, text: str, *, book_name: str = "") -> list[dict]:
        """将单个章节切分为块
        
        Returns:
            [{"chapter": title, "chunk_index": i, "content": text}, ...]
        """
        rows: list[dict] = []
        for section_index, (section_path, section_text) in enumerate(self._sections(title, text)):
            parent_id = hashlib.md5(
                f"{book_name}|{title}|{' > '.join(section_path)}|{section_index}".encode("utf-8")
            ).hexdigest()[:16]
            for child in self.splitter.split_text(section_text):
                content = child.strip()
                if not content:
                    continue
                idx = len(rows)
                chunk_id = hashlib.md5(
                    f"{book_name}|{title}|{parent_id}|{idx}|{content[:120]}".encode("utf-8")
                ).hexdigest()[:16]
                context = " > ".join(section_path)
                prefix = f"\u6559\u6750\uff1a{book_name}\n\u7ae0\u8282\u8def\u5f84\uff1a{context}\n" if book_name else f"\u7ae0\u8282\u8def\u5f84\uff1a{context}\n"
                rows.append({
                    "chapter": title,
                    "section_title": section_path[-1],
                    "section_path": section_path,
                    "chunk_index": idx,
                    "content": content,
                    "retrieval_text": f"{prefix}\u6b63\u6587\uff1a{content}",
                    "chunk_id": chunk_id,
                    "parent_id": parent_id,
                    "parent_content": section_text[:2000],
                })
        for idx, row in enumerate(rows):
            row["prev_chunk_id"] = rows[idx - 1]["chunk_id"] if idx else ""
            row["next_chunk_id"] = rows[idx + 1]["chunk_id"] if idx + 1 < len(rows) else ""
        return rows

    @staticmethod
    def _sections(title: str, text: str) -> list[tuple[list[str], str]]:
        heading = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
        path, current, result = [title], [], []

        def flush() -> None:
            body = "\n".join(current).strip()
            if body:
                result.append((list(path), body))
            current.clear()

        for line in (text or "").splitlines():
            match = heading.match(line)
            if not match:
                current.append(line)
                continue
            flush()
            depth = max(1, len(match.group(1)) - 1)
            path[:] = path[:depth]
            path.append(match.group(2).strip())
        flush()
        return result or [([title], (text or "").strip())]

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
