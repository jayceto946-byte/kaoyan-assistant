"""LaTeX validation and repair helpers for generated highlight markdown."""
from __future__ import annotations

from typing import Any
import re

from config import get_llm
from utils.latex_sanitizer import sanitize_latex
from utils.thinking_filter import strip_thinking


class ChapterHighlightLatexMixin:
    """Sanitizes generated markdown without changing its educational content."""

    def _sanitize_generated_markdown(self, raw: Any, context_title: str = "", allow_llm_repair: bool = True) -> str:
        text = strip_thinking(str(raw or "")).replace("＄", "$")
        text = re.sub(r'\[IMAGE:[^\]]+\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[(?:公式|图片|图像)(?:索引|编号|引用)[:：]\s*[^\]]+\]', '', text)
        text = re.sub(r'\\(?:tag\*?|label|ref|eqref)\s*\{[^{}]*\}', '', text)
        text = sanitize_latex(text)
        text = self._normalize_display_math(text)
        text = self._remove_empty_math(text)
        issues = self._latex_validation_issues(text)
        if issues and allow_llm_repair:
            repaired = self._repair_latex_with_llm(text, issues, context_title)
            if repaired:
                repaired = sanitize_latex(strip_thinking(repaired).replace("＄", "$"))
                repaired = self._normalize_display_math(repaired)
                repaired = self._remove_empty_math(repaired)
                repaired_issues = self._latex_validation_issues(repaired)
                if len(repaired_issues) <= len(issues):
                    text = repaired
                    issues = repaired_issues
        if issues:
            text = self._local_latex_fallback(text)
        return sanitize_latex(text).strip()

    def _repair_latex_with_llm(self, markdown: str, issues: list[str], context_title: str = "") -> str:
        issue_text = "\n".join(f"- {issue}" for issue in issues[:6])
        prompt = f"""你是 Markdown/LaTeX 格式修复器，只修复公式定界符和明显的 LaTeX 格式错误，不改写知识内容，不增删重点，不输出解释。\n\n范围：{context_title or '章节重点'}\n\n发现的问题：\n{issue_text}\n\n修复规则：\n1. 独立公式必须使用单独成行的 $$ ... $$，不要和中文解释同一行混排。\n2. 行内公式只包裹纯数学表达式；中文解释放在 $ 外，必要时才使用 \\text{{...}}。\n3. 删除空的 $ $ 或 $$ $$，补齐缺失的成对定界符。\n4. 保留原有 Markdown 层级和来源标注。\n\n原文：\n```markdown\n{markdown}\n```\n"""
        try:
            return str(get_llm(temperature=0).invoke(prompt).content or "")
        except Exception:
            return ""

    def _latex_validation_issues(self, markdown: str) -> list[str]:
        text = str(markdown or "")
        if not text.strip():
            return []
        issues: list[str] = []
        if re.search(r"(?<!\\)\$\$\s*(?<!\\)\$\$", text, flags=re.DOTALL):
            issues.append("存在空的独立公式定界符")
        if re.search(r"(?<!\\)(?<!\$)\$(?!\$)\s*(?<!\\)(?<!\$)\$(?!\$)", text, flags=re.DOTALL):
            issues.append("存在空的行内公式定界符")
        display_count = len(re.findall(r"(?<!\\)\$\$", text))
        if display_count % 2:
            issues.append("独立公式 $$ 定界符数量不成对")
        without_display = re.sub(r"(?<!\\)\$\$.*?(?<!\\)\$\$", " ", text, flags=re.DOTALL)
        inline_count = len(re.findall(r"(?<!\\)(?<!\$)\$(?!\$)", without_display))
        if inline_count % 2:
            issues.append("行内公式 $ 定界符数量不成对")
        mathless = self._strip_math_segments(text)
        if re.search(r"\\begin\{(?:aligned|matrix|pmatrix|bmatrix|cases|array|equation|gather|split)\}", mathless):
            issues.append("LaTeX 环境疑似出现在数学模式外")
        for segment in self._math_segments(text):
            stripped = re.sub(r"\\(?:text|mathrm|operatorname)\{[^{}]*\}", "", segment)
            if re.search(r"[\u4e00-\u9fff]", stripped):
                issues.append("数学模式中含有未包裹的中文")
                break
        return issues

    def _normalize_display_math(self, markdown: str) -> str:
        def replace(match: re.Match[str]) -> str:
            body = match.group(1).strip()
            if not body:
                return ""
            return f"\n$$\n{body}\n$$\n"

        text = re.sub(r"(?<!\\)\$\$(.*?)(?<!\\)\$\$", replace, str(markdown or ""), flags=re.DOTALL)
        return re.sub(r"\n{3,}", "\n\n", text)

    def _remove_empty_math(self, markdown: str) -> str:
        text = re.sub(r"(?<!\\)\$\$\s*(?<!\\)\$\$", "", str(markdown or ""), flags=re.DOTALL)
        text = re.sub(r"(?<!\\)(?<!\$)\$(?!\$)\s*(?<!\\)(?<!\$)\$(?!\$)", "", text, flags=re.DOTALL)
        return text

    def _local_latex_fallback(self, markdown: str) -> str:
        text = self._remove_empty_math(str(markdown or "").replace("＄", "$"))
        return sanitize_latex(text)

    def _math_segments(self, markdown: str) -> list[str]:
        text = str(markdown or "")
        segments = [match.group(1) for match in re.finditer(r"(?<!\\)\$\$(.*?)(?<!\\)\$\$", text, flags=re.DOTALL)]
        text = re.sub(r"(?<!\\)\$\$.*?(?<!\\)\$\$", " ", text, flags=re.DOTALL)
        segments.extend(
            match.group(1)
            for match in re.finditer(r"(?<!\\)(?<!\$)\$(?!\$)(.*?)(?<!\\)(?<!\$)\$(?!\$)", text, flags=re.DOTALL)
        )
        return segments

    def _strip_math_segments(self, markdown: str) -> str:
        text = re.sub(r"(?<!\\)\$\$.*?(?<!\\)\$\$", " ", str(markdown or ""), flags=re.DOTALL)
        return re.sub(r"(?<!\\)(?<!\$)\$(?!\$).*?(?<!\\)(?<!\$)\$(?!\$)", " ", text, flags=re.DOTALL)

