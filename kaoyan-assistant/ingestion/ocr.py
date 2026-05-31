"""多模态模块 - PDF图片提取 + 公式OCR + 扫描件识别"""
import base64
import io
import os
from pathlib import Path
import fitz
from PIL import Image

from config import IMAGES_PATH, BOOKS_PATH, MULTIMODAL_ENABLED, get_llm_client


class PDFImageExtractor:
    """从PDF中提取图片，用于扫描件/公式的视觉理解"""

    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        self.doc = fitz.open(self.pdf_path)
        self.output_dir = Path(IMAGES_PATH) / self.pdf_path.stem
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_page_images(self, page_number: int) -> list[Path]:
        """提取指定页面中的嵌入图片"""
        page = self.doc[page_number]
        images = page.get_images(full=True)
        paths = []
        for idx, img in enumerate(images):
            xref = img[0]
            base_image = self.doc.extract_image(xref)
            ext = base_image["ext"]
            img_path = self.output_dir / f"p{page_number + 1}_img{idx}.{ext}"
            with open(img_path, "wb") as f:
                f.write(base_image["image"])
            paths.append(img_path)
        return paths

    def render_page_as_image(self, page_number: int, dpi: int = 200) -> Path:
        """将PDF页面渲染为图片（用于扫描件识别）"""
        page = self.doc[page_number]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_path = self.output_dir / f"p{page_number + 1}.png"
        pix.save(str(img_path))
        return img_path

    def render_chapter_pages(self, start_page: int, end_page: int, dpi: int = 150) -> list[Path]:
        """渲染章节页面范围"""
        paths = []
        for p in range(start_page, min(end_page, len(self.doc))):
            paths.append(self.render_page_as_image(p, dpi))
        return paths

    def close(self):
        self.doc.close()


class FormulaOCR:
    """公式OCR - 使用多模态LLM识别图片中的数学公式"""

    def __init__(self):
        self.client = get_llm_client()
        self.model = os.getenv("LLM_MODEL_NAME", "kimi-k2.6")

    def _encode_image(self, image_path: str | Path) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _build_image_content(self, image_path: str | Path) -> dict:
        ext = Path(image_path).suffix.lower().replace(".", "")
        if ext == "jpg":
            ext = "jpeg"
        b64 = self._encode_image(image_path)
        return {
            "type": "image_url",
            "image_url": {"url": f"data:image/{ext};base64,{b64}"}
        }

    def extract_formulas(self, image_path: str | Path) -> str:
        """从图片中提取LaTeX公式"""
        if not MULTIMODAL_ENABLED:
            return "[多模态未启用，请配置 Kimi K2.6]"

        content = [
            {"type": "text", "text": (
                "请识别图片中的所有数学公式，以LaTeX格式输出（行内用$...$，块级用$$...$$）。"
                "如果图片是扫描版教材页面，请额外提取所有文字内容。"
            )},
            self._build_image_content(image_path),
        ]

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
        )
        return resp.choices[0].message.content

    def analyze_page(self, image_path: str | Path, context: str = "") -> str:
        """分析页面内容（配合上下文理解）"""
        if not MULTIMODAL_ENABLED:
            return "[多模态未启用]"

        ctx_text = f"\n\n上下文参考：{context}" if context else ""
        content = [
            {"type": "text", "text": (
                f"请分析这个教材页面，提取关键知识点、公式和例题。用中文总结。{ctx_text}"
            )},
            self._build_image_content(image_path),
        ]

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
        )
        return resp.choices[0].message.content

    def multimodal_ask(self, question: str, image_paths: list[str | Path],
                       context: str = "") -> str:
        """多模态问答：文本问题 + 图片 + 上下文"""
        if not MULTIMODAL_ENABLED:
            return "[多模态未启用，请配置 Kimi K2.6]"

        content = [{"type": "text", "text": (
            f"你是一个考研辅导专家。\n\n"
            f"## 上下文参考资料\n{context}\n\n"
            f"## 用户问题\n{question}\n\n"
            f"请结合上下文和图片给出详细解答。公式用LaTeX格式。"
        )}]

        for img_path in image_paths:
            content.append(self._build_image_content(img_path))

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
        )
        return resp.choices[0].message.content
