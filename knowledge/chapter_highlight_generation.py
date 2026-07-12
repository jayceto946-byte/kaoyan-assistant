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
        return f"""你是教材证据整理助手。只能整理下方提供的 OCR 正文、公式候选、图片索引和教材题目，不得使用模型记忆补充教材外知识。必须使用中文，不要寒暄，不要 thinking。

教材：{source.get('book_name')}
章节：{chapter.get('title')}
生成范围：{scope.get('title') or chapter.get('title')}
当前小节：{section_titles}

相关图片索引：
{images}

本节教材例题/习题片段：
{examples}

OCR 正文：
{section_text}

输出要求：
1. 只输出 Markdown；不要重复章节总标题，只保留必要的三级标题。
2. 先提炼定义、公式、条件、结论和方法，再整理教材已有例题/习题；不要为了填满栏目重复改写。
3. 每条事实必须能在给定材料中找到依据，并在段末标注可读来源页码，如“来源：p12”。不要输出 chunk_id、UUID、collection 名等内部标识。
4. 证据不足时明确写“本节教材材料未提供”，不得凭模型知识补齐。
5. 禁止自拟题、补充例题、生活化类比和教材外扩展；没有完整教材题时省略题目栏目。
6. 公式使用可渲染 LaTeX：行内 $...$；独立公式使用成对的 $$...$$；不得把中文放进数学模式。
7. 控制篇幅：相同结论只写一次，优先保留考研复习所需的定义、公式条件、典型方法和易错点。
8. 图片确有助于理解时才单独写 [IMAGE:img_001]，且只能使用上方已有图片 id。
"""

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
            return "未检出完整教材例题/习题；不要自拟题，省略题目栏目。"
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

