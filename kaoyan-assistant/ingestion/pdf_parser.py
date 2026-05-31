"""PDF解析模块 - 提取文本并识别章节结构"""
import re
from pathlib import Path
import fitz


class PDFParser:
    """解析PDF书籍，提取文本和章节信息"""

    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        self.doc = fitz.open(self.pdf_path)
        self.total_pages = len(self.doc)

    def extract_text(self) -> str:
        """提取全部文本"""
        text = ""
        for page in self.doc:
            text += page.get_text() + "\n"
        return text

    def extract_text_by_page(self) -> list[str]:
        """按页提取文本"""
        return [page.get_text() for page in self.doc]

    def extract_chapters(self, chapter_pattern: str | None = None) -> list[dict]:
        """基于目录/标题模式提取章节

        Args:
            chapter_pattern: 章节标题的正则模式，默认匹配 '第X章'、'第X节' 等

        Returns:
            章节列表，每项包含 {title, page_number, text}
        """
        if chapter_pattern is None:
            chapter_pattern = r"第[一二三四五六七八九十百零\d]+[章节部篇]|Chapter\s+\d+"

        toc = self.doc.get_toc()
        chapters = []

        if toc:
            # 使用PDF内置目录
            for level, title, page in toc:
                if level == 1:
                    text = self._get_page_text(page - 1)
                    chapters.append({
                        "title": title.strip(),
                        "page_number": page,
                        "text": text,
                    })
        else:
            # 基于正则匹配章节标题
            full_text = self.extract_text()
            lines = full_text.split("\n")
            current_chapter = None
            current_text = []

            for line in lines:
                if re.match(chapter_pattern, line.strip()):
                    if current_chapter:
                        chapters.append({
                            "title": current_chapter,
                            "text": "\n".join(current_text).strip(),
                        })
                    current_chapter = line.strip()
                    current_text = []
                else:
                    current_text.append(line)

            if current_chapter:
                chapters.append({
                    "title": current_chapter,
                    "text": "\n".join(current_text).strip(),
                })

        return chapters

    def _get_page_text(self, page_num: int) -> str:
        """获取指定页面的文本"""
        if 0 <= page_num < self.total_pages:
            return self.doc[page_num].get_text()
        return ""

    def close(self):
        self.doc.close()
