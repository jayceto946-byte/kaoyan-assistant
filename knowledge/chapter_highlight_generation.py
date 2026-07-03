"""LLM prompt construction and markdown generation for chapter highlights."""
from __future__ import annotations

import re

from config import get_llm
from .chapter_highlight_types import MAX_SECTION_INPUT_CHARS, ProgressCallback


class ChapterHighlightGenerationMixin:
    """Runs section prompts and combines generated notes."""

    def _generate_section_notes(self, source: dict, progress: ProgressCallback) -> list[dict]:
        sections = source.get("sections", [])
        batches: list[list[dict]] = []
        for section in sections:
            for part in self._split_section_for_prompt(section, MAX_SECTION_INPUT_CHARS):
                batches.append([part])
        notes: list[dict] = []
        total = max(1, len(batches))
        for idx, batch in enumerate(batches):
            section_title = batch[0].get("title") or "小节"
            percent = 24 + int(54 * idx / total)
            progress("sections", f"生成 {section_title} 重点 {idx + 1}/{total}", percent)
            prompt = self._section_prompt(source, batch)
            raw = get_llm(temperature=0.2).invoke(prompt).content
            text = self._sanitize_generated_markdown(raw, context_title=section_title)
            notes.append({
                "batch_index": idx,
                "section_ids": [section.get("id", "") for section in batch],
                "section_titles": [str(section.get("title") or "小节") for section in batch],
                "markdown": text,
            })
        return notes

    def _generate_final_markdown(self, source: dict, section_notes: list[dict]) -> str:
        scope = source.get("scope", {})
        chapter = source.get("chapter", {})
        is_section = scope.get("type") == "section"
        title_line = "# 本节重点" if is_section else "# 本章重点"
        scope_title = scope.get("title") or chapter.get("title", "")
        page_text = f"p{scope.get('page') or chapter.get('page')}-{scope.get('end_page') or chapter.get('end_page') or chapter.get('page')}"

        lines = [
            title_line,
            "",
            f"> 教材：{source.get('book_name')}  ",
            f"> 范围：{scope_title}  ",
            f"> 页码：{page_text}",
            "",
        ]

        ordered_sections = self._ordered_section_markdowns(source, section_notes)
        for item in ordered_sections:
            lines.extend([f"## {item['title']}", ""])
            body = str(item.get("markdown") or "").strip()
            if body:
                lines.extend([body, ""])

        if not ordered_sections:
            for note in sorted(section_notes, key=self._note_order):
                body = self._normalize_section_note_markdown(str(note.get("markdown") or ""), "小节重点")
                if body:
                    lines.extend(["## 小节重点", "", body, ""])

        return self._sanitize_generated_markdown("\n".join(lines).strip(), context_title=scope_title, allow_llm_repair=False)

    def _ordered_section_markdowns(self, source: dict, section_notes: list[dict]) -> list[dict]:
        notes_by_section: dict[str, list[dict]] = {}
        for note in section_notes:
            markdown = str(note.get("markdown") or "").strip()
            if not markdown:
                continue
            section_ids = [str(value).strip() for value in note.get("section_ids", []) if str(value).strip()]
            if not section_ids:
                continue
            notes_by_section.setdefault(section_ids[0], []).append(note)

        ordered: list[dict] = []
        for section in source.get("sections", []):
            section_id = str(section.get("id") or "").strip()
            if not section_id:
                continue
            notes = sorted(notes_by_section.get(section_id, []), key=self._note_order)
            if not notes:
                continue
            title = str(section.get("title") or "小节重点").strip()
            parts = [
                self._normalize_section_note_markdown(str(note.get("markdown") or ""), title)
                for note in notes
            ]
            body = self._dedupe_markdown_blocks("\n\n".join(part for part in parts if part).strip())
            if body:
                ordered.append({"id": section_id, "title": title, "markdown": body})
        return ordered

    def _note_order(self, note: dict) -> int:
        try:
            return int(note.get("batch_index") or 0)
        except Exception:
            return 0

    def _normalize_section_note_markdown(self, markdown: str, section_title: str) -> str:
        text = self._sanitize_generated_markdown(markdown, context_title=section_title, allow_llm_repair=False)
        kept: list[str] = []
        skip_level: int | None = None
        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            level = len(heading.group(1)) if heading else 0
            if skip_level is not None:
                if heading and level <= skip_level:
                    skip_level = None
                else:
                    continue
            if heading:
                title = self._clean_generated_heading(heading.group(2))
                if self._is_unwanted_highlight_heading(title):
                    skip_level = level
                    continue
                if level <= 2:
                    continue
            kept.append(line)
        return self._dedupe_markdown_blocks("\n".join(kept).strip())

    def _clean_generated_heading(self, title: str) -> str:
        title = re.sub(r"`([^`]+)`", r"\1", str(title or ""))
        title = re.sub(r"\*\*([^*]+)\*\*", r"\1", title)
        title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", title)
        title = re.sub(r"\$+", "", title)
        return re.sub(r"\s+", "", title).strip()

    def _is_unwanted_highlight_heading(self, title: str) -> bool:
        compact = self._clean_generated_heading(title)
        unwanted = (
            "本章重点",
            "本节重点",
            "分节重点",
            "总章节",
            "章节总览",
            "整体总结",
            "本章总结",
            "本章学习要点参考",
            "本章学习要点",
            "学习要点参考",
            "教材例题与习题资源",
        )
        return any(token in compact for token in unwanted)

    def _dedupe_markdown_blocks(self, markdown: str) -> str:
        blocks = re.split(r"\n{2,}", str(markdown or "").strip())
        seen: set[str] = set()
        kept: list[str] = []
        for block in blocks:
            normalized = re.sub(r"\s+", " ", block).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            kept.append(block.strip())
        return "\n\n".join(kept)

    def _section_prompt(self, source: dict, sections: list[dict]) -> str:
        chapter = source["chapter"]
        scope = source.get("scope", {})
        section_text = "\n\n".join(self._format_section_for_prompt(section) for section in sections)
        images = self._section_images_text(source, sections)
        examples = self._section_examples_text(sections)
        section_titles = " / ".join(str(section.get("title") or "小节") for section in sections)
        return f"""你是考研数学与专业课教材重点整理助手。请基于给定 OCR 正文，为下面小节生成可直接复习的详细重点页。必须使用中文输出。不要寒暄，不要 thinking。\n\n教材：{source.get('book_name')}\n章节：{chapter.get('title')}\n生成范围：{scope.get('title') or chapter.get('title')}\n当前小节：{section_titles}\n\n相关图片索引：\n{images}\n\n本节教材例题/习题片段：\n{examples}\n\nOCR 正文：\n{section_text}\n\n输出要求：\n1. 只输出 Markdown。只允许使用上方 OCR 正文对应的小节标题作为唯一的二级标题“## 小节标题”；不要输出“# 本章重点”“# 本节重点”“## 分节重点”“## 总章节”“## 整体总结”。\n2. 不要输出“教材例题与习题资源”“本章学习要点参考”“本章学习要点”这些附录式栏目。\n3. 内容要比普通摘要更完整：核心概念写定义、适用条件、常见考法；公式写变量含义、成立条件和使用限制；方法步骤能指导做题。\n4. 遇到学习者可能第一次接触、或本身比较抽象陌生的概念时，在“核心概念与公式”中补一句“直观例子”或“生活化类比”，用日常场景说明它具体怎么体现；例子要简短准确，不能替代教材定义、公式条件或后面的解题过程。\n5. 小节内固定结构：### 知识点地图、### 核心概念与公式、### 方法步骤、### 以题讲知识点、### 典型考法、### 易错点、### 复习清单。\n6. “知识点地图”不要写成术语清单，要说明概念之间如何服务于后续题目、公式或方法步骤。\n7. “以题讲知识点”必须有题，并作为本节重点的主线：若上方教材例题/习题片段里有相对完整题目，选一道最能覆盖本节方法的教材题，写题目摘录、考点、解法步骤、易错点和来源；若没有完整题目，可以生成一道“自拟巩固题”，但必须明确标注“自拟巩固题”，且只能基于本节材料。不要把重点页主要写成概念罗列。\n8. 如图片、表格、流程图对理解有帮助，必须在对应位置单独写一行 [IMAGE:img_001] 这样的占位符；只能使用上方图片 id，不要编造图片编号。\n9. 公式在生成阶段就要校正为可渲染 LaTeX：行内公式使用 $...$；独立公式必须单独成行，格式为 $$ 换行 公式 换行 $$。不要把中文解释放进数学模式，不要输出空公式、半截美元符号或中文全角美元符号。\n10. 每个重点、公式、例题或方法后尽量标注来源页码或 chunk_id，如“来源：p12 / chunk_3”。\n"""

    def _format_section_for_prompt(self, section: dict) -> str:
        lines = [f"## {section.get('title') or '未命名小节'}"]
        for chunk in section.get("chunks", []):
            text = str(chunk.get("text") or "").strip()
            if not text:
                continue
            ref = chunk.get("source_ref") or chunk.get("chunk_id") or ""
            role = chunk.get("role") or "reference"
            page = chunk.get("page") or ""
            lines.append(f"\n[来源 {ref}; page={page}; role={role}]\n{text}")
            equations = chunk.get("equations") or []
            if equations:
                rendered = []
                for item in equations[:8]:
                    if isinstance(item, dict):
                        rendered.append(str(item.get("formula_latex") or item.get("latex") or item.get("text") or item))
                    else:
                        rendered.append(str(item))
                lines.append("[公式候选]\n" + "\n".join(rendered))
        return "\n".join(lines)

    def _practice_appendix_markdown(self, source: dict) -> str:
        lines: list[str] = []
        chunks: list[dict] = []
        for section in source.get("practice_sections", []):
            for chunk in section.get("chunks", []):
                chunks.append(chunk)
        if not chunks:
            return ""
        for chunk in chunks[:12]:
            text = str(chunk.get("text") or "").strip()
            if not text:
                continue
            if len(text) > 700:
                text = text[:700] + "……"
            ref = chunk.get("source_ref") or chunk.get("chunk_id") or ""
            lines.append(f"- 来源 {ref}：{text}")
        if len(chunks) > 12:
            lines.append(f"- 其余 {len(chunks) - 12} 个习题片段已省略，可回到教材习题页继续整理。")
        return "\n".join(lines)

    def _section_examples_text(self, sections: list[dict], max_chars: int = 5000) -> str:
        candidates: list[str] = []
        for section in sections:
            for chunk in section.get("chunks", []):
                text = str(chunk.get("text") or "").strip()
                role = str(chunk.get("role") or "")
                if role in {"example", "exercise"} or self._looks_like_problem(text):
                    ref = chunk.get("source_ref") or chunk.get("chunk_id") or ""
                    candidates.append(f"[来源 {ref}; role={role or 'problem'}]\n{text}")
        if not candidates:
            return "未检出完整教材例题/习题；本节可以生成一道明确标注的自拟巩固题。"
        text = "\n\n".join(candidates)
        return text[:max_chars] + ("\n\n[例题/习题片段因长度限制已截断。]" if len(text) > max_chars else "")

    def _section_images_text(self, source: dict, sections: list[dict]) -> str:
        images = [image for image in source.get("image_refs", []) if any(self._image_in_section(image, section) for section in sections)]
        if not images:
            return "无"
        return "\n".join(
            f"- {img['id']}: page {img.get('page')}, path={img.get('path')}, caption={img.get('caption') or '无'}"
            for img in images
        )

    def _split_section_for_prompt(self, section: dict, max_chars: int) -> list[dict]:
        if len(self._format_section_for_prompt(section)) <= max_chars:
            return [section]
        base = {key: value for key, value in section.items() if key != "chunks"}
        parts: list[dict] = []
        current: list[dict] = []
        for chunk in section.get("chunks", []):
            candidate = {**base, "chunks": current + [chunk]}
            if current and len(self._format_section_for_prompt(candidate)) > max_chars:
                parts.append({**base, "chunks": current})
                current = []
            current.append(chunk)
        if current:
            parts.append({**base, "chunks": current})
        total = len(parts)
        for index, part in enumerate(parts):
            part["part_index"] = index
            part["part_count"] = total
            if total > 1:
                part["title"] = f"{section.get('title') or '小节'}（{index + 1}/{total}）"
        return parts or [section]

    def _section_batches(self, sections: list[dict], max_chars: int) -> list[list[dict]]:
        batches: list[list[dict]] = []
        current: list[dict] = []
        current_len = 0
        for section in sections:
            for part in self._split_section_for_prompt(section, max_chars):
                text_len = len(self._format_section_for_prompt(part))
                if current and current_len + text_len > max_chars:
                    batches.append(current)
                    current = []
                    current_len = 0
                current.append(part)
                current_len += text_len
        if current:
            batches.append(current)
        return batches

