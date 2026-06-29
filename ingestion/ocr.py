"""OCR 模块 — PaddleOCR + PPStructure 引擎（本地，无 API 调用）"""
import base64
import re
import os
from pathlib import Path
from typing import Optional

import fitz

from config import IMAGES_PATH, BOOKS_PATH


class PDFImageExtractor:
    """PDF 图片提取（兼容旧代码）"""
    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        self.doc = fitz.open(self.pdf_path)
        self.output_dir = Path(IMAGES_PATH) / self.pdf_path.stem
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def render_page_as_image(self, page_number: int, dpi: int = 200) -> Path:
        page = self.doc[page_number]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_path = self.output_dir / f"p{page_number + 1}.png"
        pix.save(str(img_path))
        return img_path

    def close(self):
        self.doc.close()

try:
    from paddleocr import PaddleOCR
    _PADDLE_AVAILABLE = True
    _PADDLE_IMPORT_ERROR = None
except Exception as e:
    PaddleOCR = None
    _PADDLE_AVAILABLE = False
    _PADDLE_IMPORT_ERROR = e

try:
    from paddleocr import PPStructure
    _PPSTRUCTURE_AVAILABLE = True
    _PPSTRUCTURE_IMPORT_ERROR = None
except Exception as e:
    PPStructure = None
    _PPSTRUCTURE_AVAILABLE = False
    _PPSTRUCTURE_IMPORT_ERROR = e


class PaddleOCREngine:
    """PaddleOCR 引擎封装

    - PaddleOCR: 快速文字识别
    - PPStructure: 版面分析（标题/正文/表格/图片区域）
    """

    def __init__(self, use_structure: bool = True):
        self._ocr: Optional[PaddleOCR] = None
        self._structure: Optional[PPStructure] = None
        self.use_structure = use_structure and _PPSTRUCTURE_AVAILABLE
        self.available = _PADDLE_AVAILABLE

    @property
    def ocr(self):
        if self._ocr is None and _PADDLE_AVAILABLE:
            self._ocr = PaddleOCR(lang="ch")
        return self._ocr

    @property
    def structure(self):
        if self._structure is None and self.use_structure:
            self._structure = PPStructure(show_log=False, layout=True)
        return self._structure

    def extract_text(self, image_path: str | Path) -> str:
        if not self.available:
            detail = f": {_PADDLE_IMPORT_ERROR}" if _PADDLE_IMPORT_ERROR else ""
            return f"[PaddleOCR 不可用{detail}]"
        result = self.ocr.ocr(str(image_path))
        item = result[0] if result else None
        if item is None:
            return ""

        texts = item.get("rec_texts", []) or []
        polys = item.get("rec_polys", []) or []

        if not polys or len(polys) != len(texts):
            return "\n".join(str(t) for t in texts)

        pairs = sorted(
            (sum(p[1] for p in polys[i]) / len(polys[i]), str(texts[i]))
            for i in range(len(texts)) if i < len(polys) and len(polys[i]) >= 4
        )
        return "\n".join(t for _, t in pairs)

    def extract_toc_lines(self, image_path: str | Path) -> str:
        """专用于目录页：双栏检测 + 同行合并 + 过滤 leader dots"""
        if not self.available:
            return ""
        result = self.ocr.ocr(str(image_path))
        item = result[0] if result else None
        if item is None:
            return ""

        texts = item.get("rec_texts", []) or []
        polys = item.get("rec_polys", []) or []

        # 收集所有块的位置
        blocks = []
        for i, t in enumerate(texts):
            if i >= len(polys) or len(polys[i]) < 4:
                continue
            poly = polys[i]
            x_mid = sum(p[0] for p in poly) / len(poly)
            y_mid = sum(p[1] for p in poly) / len(poly)
            blocks.append((x_mid, y_mid, str(t)))

        if not blocks:
            return ""

        # 列检测：收集所有 X 坐标，找中位数作为左右分界
        xs = sorted(b[0] for b in blocks)
        if len(xs) < 10:
            return self._merge_rows(blocks)

        # 用 K-Means 思路：X 分成两组，间距 > 页面宽度的 15%
        x_range = xs[-1] - xs[0]
        gap_threshold = x_range * 0.15
        split_x = None
        for i in range(1, len(xs)):
            if xs[i] - xs[i - 1] > gap_threshold:
                split_x = (xs[i] + xs[i - 1]) / 2
                break

        if split_x is None:
            return self._merge_rows(blocks)

        # 拆左右栏
        left = [b for b in blocks if b[0] < split_x]
        right = [b for b in blocks if b[0] >= split_x]

        if len(right) < 3:
            return self._merge_rows(blocks)

        left_lines = self._merge_rows(left)
        right_lines = self._merge_rows(right)
        return left_lines + "\n" + right_lines

    def _merge_rows(self, blocks: list) -> str:
        """同一栏内：按 Y 分组合并同行文本，行尾纯数字=页码"""
        rows = {}
        for x_mid, y_mid, txt in blocks:
            key = round(y_mid / 15) * 15
            rows.setdefault(key, []).append((x_mid, txt))

        lines = []
        for y in sorted(rows.keys()):
            items = sorted(rows[y], key=lambda b: b[0])
            title_parts = []
            page_num = ""

            for x_mid, txt in items:
                stripped = txt.strip()
                # 纯数字 + 短 + 出现在行尾（右半侧）= 页码
                if stripped.isdigit() and len(stripped) <= 4:
                    if title_parts:
                        page_num = stripped
                    else:
                        title_parts.append(stripped)
                elif re.match(r'^[.…\-—／\s]+$', stripped):
                    continue
                else:
                    title_parts.append(stripped)

            line = "".join(title_parts).strip()
            if page_num:
                line += f"  [{page_num}]"
            if line and len(line) > 1 and not re.match(r'^[\d\s.,;:]*$', line):
                lines.append(line)

        return "\n".join(lines)

    def extract_with_bbox(self, image_path: str | Path) -> list[dict]:
        if not self.available:
            return []
        result = self.ocr.ocr(str(image_path))
        item = result[0] if result else None
        if item is None:
            return []

        texts = item.get("rec_texts", []) or []
        scores = item.get("rec_scores", []) or []
        polys = item.get("rec_polys", []) or []

        pairs = []
        for i, t in enumerate(texts):
            box = polys[i] if i < len(polys) else []
            if box and len(box) >= 4:
                y_center = sum(p[1] for p in box) / len(box)
                pairs.append((y_center, box, str(t), scores[i] if i < len(scores) else 0))

        pairs.sort()
        return [{"bbox": p[1], "text": p[2], "confidence": p[3]} for p in pairs]
        if not result or not result[0]:
            return []
        return [
            {"bbox": line[0], "text": line[1][0], "confidence": line[1][1]}
            for line in result[0] if line and len(line) > 1
        ]

    def analyze_layout(self, image_path: str | Path) -> list[dict]:
        """PPStructure 版面分析

        Returns: [
          {"type": "title"|"text"|"table"|"figure",
           "text": "...",
           "bbox": [x0,y0,x1,y1],
           "page": 1},
        ]
        """
        if not self.use_structure:
            return self._fallback_layout(image_path)

        import cv2
        img = cv2.imread(str(image_path))
        if img is None:
            return self._fallback_layout(image_path)

        result = self.structure(img)
        items = []
        for r in result:
            tp = r.get("type", "text")
            txt = ""
            if tp == "table":
                txt = r.get("res", {}).get("html", "")
            else:
                for block in r.get("res", []):
                    if isinstance(block, dict):
                        txt += block.get("text", "") + "\n"
                    elif isinstance(block, list):
                        for b in block:
                            txt += str(b.get("text", "")) + "\n"
            items.append({
                "type": tp,
                "text": txt.strip(),
                "bbox": r.get("bbox", []),
            })
        return items

    def _fallback_layout(self, image_path: str | Path) -> list[dict]:
        """无 PPStructure 时：PaddleOCR 文本 + 字体大小简单分类"""
        result = self.extract_with_bbox(image_path)
        if not result:
            return []
        return [{"type": "text", "text": r["text"], "bbox": r["bbox"]}
                for r in result]

    def extract_formula(self, image_path: str | Path) -> str:
        """提取公式（PaddleOCR 对数学公式效果一般，Kimi 更好）"""
        return self.extract_text(image_path)

    # ---------- PDF 页面渲染 ----------

    def pdf_page_to_image(self, pdf_path: str | Path, page_num: int,
                          dpi: int = 150) -> Path:
        """PDF 单页 → PNG"""
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        out_dir = Path(IMAGES_PATH) / Path(pdf_path).stem
        out_dir.mkdir(parents=True, exist_ok=True)
        img_path = out_dir / f"p{page_num + 1}.png"
        pix.save(str(img_path))
        doc.close()
        return img_path

    def pdf_pages_to_images(self, pdf_path: str | Path,
                            start: int, end: int,
                            dpi: int = 150) -> list[Path]:
        """PDF 连续页面 → PNG 列表"""
        paths = []
        doc = fitz.open(pdf_path)
        for p in range(start, min(end, len(doc))):
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = doc[p].get_pixmap(matrix=mat)
            out_dir = Path(IMAGES_PATH) / Path(pdf_path).stem
            out_dir.mkdir(parents=True, exist_ok=True)
            img_path = out_dir / f"p{p + 1}.png"
            pix.save(str(img_path))
            paths.append(img_path)
        doc.close()
        return paths


class FormulaOCR:
    """多模态 OCR 接口 — 兼容旧代码，自动选 PaddleOCR 或 Kimi"""

    def __init__(self):
        self.paddle = PaddleOCREngine()

    def extract_formulas(self, image_path: str | Path) -> str:
        if self.paddle.available:
            return self.paddle.extract_text(image_path)
        return "[请安装 PaddleOCR: pip install paddlepaddle paddleocr]"

    def multimodal_ask(self, question: str, image_paths: list[str],
                       context: str = "") -> str:
        """多模态问答：用 PaddleOCR 提取文字 → 拼接上下文 → LLM 回答"""
        ocr_texts = []
        for img in image_paths:
            ocr_texts.append(self.paddle.extract_text(img))
        combined_ocr = "\n\n".join(ocr_texts)

        from config import get_llm
        llm = get_llm()
        prompt = (
            f"## 上下文\n{context}\n\n"
            f"## 图片OCR结果\n{combined_ocr}\n\n"
            f"## 问题\n{question}\n\n"
            f"请根据以上信息回答。"
        )
        resp = llm.invoke(prompt)
        return resp.content
