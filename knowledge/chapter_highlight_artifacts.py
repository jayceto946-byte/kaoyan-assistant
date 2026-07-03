"""Markdown and HTML artifact writing for chapter highlights."""
from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path

from .chapter_highlight_types import _url_quote


class ChapterHighlightArtifactMixin:
    """Finalizes markdown, writes artifacts, and renders standalone HTML."""

    def _write_highlight_artifacts(self, base: Path, book_name: str, markdown: str, source: dict, metadata: dict, highlight: dict) -> None:
        html_doc = self._build_highlight_html(book_name, markdown, source, metadata)
        (base / "highlight.md").write_text(markdown, encoding="utf-8")
        (base / "highlight.html").write_text(html_doc, encoding="utf-8")
        self._write_json(base / "highlight.json", highlight)
        self._write_json(base / "metadata.json", metadata)

    def _finalize_markdown(self, book_name: str, markdown: str, source: dict) -> str:
        image_map = {img["id"]: img for img in source.get("image_refs", [])}
        referenced: set[str] = set()

        def image_markdown(image: dict) -> str:
            url = self._asset_url(book_name, image)
            caption = str(image.get("caption") or f"{image.get('id')} · p{image.get('page')}").strip()
            return f"![{caption}]({url})\n\n*图源：{image.get('id')}，p{image.get('page')}*"

        def replace_image(match: re.Match[str]) -> str:
            image_id = match.group(1)
            image = image_map.get(image_id)
            if not image:
                return match.group(0)
            referenced.add(image_id)
            return image_markdown(image)

        markdown = re.sub(r"\[IMAGE:(img_\d{3})\]", replace_image, markdown)
        missing = [img for img in source.get("image_refs", []) if img.get("id") not in referenced]
        if missing:
            lines = [markdown.strip(), "", "## 图表索引", ""]
            for image in missing:
                lines.append(image_markdown(image))
                lines.append("")
            markdown = "\n".join(lines)
        return self._sanitize_generated_markdown(markdown.strip(), allow_llm_repair=False)

    def _asset_url(self, book_name: str, image: dict) -> str:
        return f"/api/books/{_url_quote(book_name)}/chapter-highlights/assets/{str(image.get('path') or '').lstrip('/')}"

    def _html_url(self, book_name: str, chapter_id: str, section_id: str | None = None) -> str:
        url = f"/api/books/{_url_quote(book_name)}/chapter-highlights/{_url_quote(chapter_id)}/html"
        scope_id = self._scope_id(section_id)
        if scope_id != "all":
            url += f"?section_id={_url_quote(scope_id)}"
        return url

    def _build_highlight_html(self, book_name: str, markdown: str, source: dict, metadata: dict) -> str:
        scope = source.get("scope", {})
        title = scope.get("title") or source.get("chapter", {}).get("title") or "章节重点"
        body, toc = self._markdown_to_html_with_toc(markdown)
        generated = metadata.get("completed_at") or metadata.get("updated_at") or ""
        local_path = metadata.get("html_path") or "highlight.html"
        toc_items = "\n".join(
            f'<a class="toc-link toc-level-{item["level"]}" href="#{html.escape(item["id"], quote=True)}">{html.escape(item["title"])}</a>'
            for item in toc
        ) or '<div class="toc-empty">暂无可跳转标题</div>'
        style = """
:root { color-scheme: light; --ink:#1f2824; --muted:#65736c; --line:#d7ded5; --paper:#fffefa; --soft:#f4f6f1; --subtle:#eef3eb; --accent:#2f6f62; --accent-soft:#edf6f2; --warn:#9a6a20; }
* { box-sizing: border-box; }
html { scroll-behavior: auto; }
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif; color: var(--ink); background: var(--soft); line-height: 1.75; }
.shell { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 22px; max-width: 1280px; margin: 0 auto; padding: 28px 22px 56px; }
.toc { position: sticky; top: 22px; align-self: start; max-height: calc(100vh - 44px); overflow: auto; border: 1px solid var(--line); background: rgba(255,254,250,0.92); padding: 16px; }
.toc-title { margin: 0 0 10px; font-size: 14px; font-weight: 700; }
.toc-link { display: block; border-left: 2px solid transparent; padding: 5px 6px 5px 10px; color: var(--muted); text-decoration: none; font-size: 13px; line-height: 1.45; }
.toc-link:hover { border-left-color: var(--accent); color: var(--accent); background: var(--accent-soft); }
.toc-level-3 { padding-left: 22px; font-size: 12px; }
.toc-empty { color: var(--muted); font-size: 13px; }
.document { min-width: 0; }
.header { border-bottom: 2px solid var(--accent); padding: 10px 0 18px; margin-bottom: 20px; }
.header h1 { margin: 0 0 8px; font-size: 28px; line-height: 1.3; }
.meta { color: var(--muted); font-size: 13px; }
.local-path { margin-top: 6px; overflow-wrap: anywhere; color: var(--muted); font-size: 12px; }
article { background: var(--paper); border: 1px solid var(--line); padding: 30px; }
h1, h2, h3, h4 { scroll-margin-top: 24px; line-height: 1.35; color: #17211d; }
h1 { font-size: 26px; border-bottom: 1px solid var(--line); padding-bottom: 12px; }
h2 { margin-top: 34px; font-size: 22px; border-left: 4px solid var(--accent); padding-left: 10px; }
h3 { margin-top: 24px; font-size: 17px; }
p { margin: 10px 0; }
blockquote { margin: 14px 0; padding: 10px 14px; border-left: 4px solid var(--line); background: var(--subtle); color: var(--muted); }
ul, ol { padding-left: 1.5rem; }
li { margin: 5px 0; }
code { background: var(--subtle); border: 1px solid var(--line); border-radius: 4px; padding: 1px 4px; }
pre { overflow-x: auto; background: #17211d; color: #f9fafb; padding: 14px; }
.math-block { overflow-x: auto; margin: 14px 0; padding: 4px 0; }
figure { margin: 18px 0; border: 1px solid var(--line); background: var(--subtle); padding: 10px; }
figure img { display: block; max-width: 100%; height: auto; margin: 0 auto; }
figcaption { margin-top: 8px; color: var(--muted); font-size: 13px; text-align: center; }
hr { border: 0; border-top: 1px solid var(--line); margin: 28px 0; }
.mathjax-missing .math-block::after { content: "公式渲染脚本未加载，可在应用内重点页查看本地 KaTeX 渲染。"; display: block; margin-top: 4px; color: var(--warn); font-size: 12px; }
@media (max-width: 900px) { .shell { display: block; padding: 18px 14px 42px; } .toc { position: static; max-height: 220px; margin-bottom: 16px; } article { padding: 20px; } }
@media print { body { background:#fff; } .shell { display: block; max-width: none; padding: 0; } .toc { display: none; } article { border: 0; padding: 0; } }
"""
        mathjax_loader = """
<script>
window.MathJax = {
  tex: {
    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
    processEscapes: true
  },
  options: { skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'] },
  svg: { fontCache: 'global' }
};
(function () {
  var sources = [
    'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js',
    'https://cdn.bootcdn.net/ajax/libs/mathjax/3.2.2/es5/tex-svg.min.js'
  ];
  function load(index) {
    if (index >= sources.length) {
      document.documentElement.classList.add('mathjax-missing');
      return;
    }
    var script = document.createElement('script');
    script.src = sources[index];
    script.async = true;
    script.onerror = function () { load(index + 1); };
    document.head.appendChild(script);
  }
  load(0);
})();
</script>
"""
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{html.escape(str(title))} - 章节重点</title>
<style>{style}</style>
{mathjax_loader}
</head>
<body>
<div class="shell">
  <nav class="toc" aria-label="章节重点目录">
    <div class="toc-title">目录</div>
    {toc_items}
  </nav>
  <main class="document">
    <header class="header">
      <h1>{html.escape(str(title))}</h1>
      <div class="meta">教材：{html.escape(str(book_name))} · 生成时间：{html.escape(str(generated))}</div>
      <div class="local-path">本地文件：{html.escape(str(local_path))}</div>
    </header>
    <article>{body}</article>
  </main>
</div>
</body>
</html>"""

    def _markdown_to_html(self, markdown: str) -> str:
        body, _ = self._markdown_to_html_with_toc(markdown)
        return body

    def _markdown_to_html_with_toc(self, markdown: str) -> tuple[str, list[dict]]:
        html_lines: list[str] = []
        toc: list[dict] = []
        heading_counts: dict[str, int] = {}
        in_ul = False
        in_ol = False
        in_code = False
        in_math = False
        code_lines: list[str] = []
        math_lines: list[str] = []

        def close_lists() -> None:
            nonlocal in_ul, in_ol
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False

        def flush_math() -> None:
            nonlocal in_math, math_lines
            html_lines.append('<div class="math-block">' + html.escape("\n".join(math_lines)) + '</div>')
            math_lines = []
            in_math = False

        for raw_line in markdown.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if stripped.startswith("```"):
                if in_code:
                    html_lines.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
                    code_lines = []
                    in_code = False
                else:
                    close_lists()
                    in_code = True
                continue
            if in_code:
                code_lines.append(line)
                continue
            if in_math:
                math_lines.append(line)
                if stripped.endswith("$$"):
                    flush_math()
                continue
            if stripped.startswith("$$"):
                close_lists()
                math_lines = [line]
                if stripped.endswith("$$") and len(stripped) > 2:
                    flush_math()
                else:
                    in_math = True
                continue
            if not stripped:
                close_lists()
                continue
            if stripped == "---":
                close_lists()
                html_lines.append("<hr />")
                continue
            image_match = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
            if image_match:
                close_lists()
                alt = html.escape(image_match.group(1))
                src = html.escape(image_match.group(2), quote=True)
                html_lines.append(f'<figure><img src="{src}" alt="{alt}" /><figcaption>{alt}</figcaption></figure>')
                continue
            heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            if heading:
                close_lists()
                level = len(heading.group(1))
                title_text = heading.group(2).strip()
                heading_id = self._heading_id(title_text, level, heading_counts)
                plain_title = self._plain_heading_text(title_text)
                if level == 2:
                    toc.append({"level": level, "title": plain_title, "id": heading_id})
                html_lines.append(f'<h{level} id="{heading_id}">{self._render_inline_html(title_text)}</h{level}>')
                continue
            if stripped.startswith(">"):
                close_lists()
                html_lines.append(f"<blockquote>{self._render_inline_html(stripped.lstrip('> ').strip())}</blockquote>")
                continue
            bullet = re.match(r"^[-*]\s+(.+)$", stripped)
            if bullet:
                if not in_ul:
                    close_lists()
                    html_lines.append("<ul>")
                    in_ul = True
                html_lines.append(f"<li>{self._render_inline_html(bullet.group(1))}</li>")
                continue
            ordered = re.match(r"^\d+[.)]\s+(.+)$", stripped)
            if ordered:
                if not in_ol:
                    close_lists()
                    html_lines.append("<ol>")
                    in_ol = True
                html_lines.append(f"<li>{self._render_inline_html(ordered.group(1))}</li>")
                continue
            close_lists()
            html_lines.append(f"<p>{self._render_inline_html(stripped)}</p>")
        if in_code:
            html_lines.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
        if in_math:
            flush_math()
        close_lists()
        return "\n".join(html_lines), toc

    def _heading_id(self, text: str, level: int, counts: dict[str, int]) -> str:
        plain = self._plain_heading_text(text)
        key = f"{level}:{plain}"
        counts[key] = counts.get(key, 0) + 1
        digest = hashlib.sha1(f"{key}:{counts[key]}".encode("utf-8")).hexdigest()[:10]
        return f"sec-{digest}"

    def _plain_heading_text(self, text: str) -> str:
        text = re.sub(r"`([^`]+)`", r"\1", text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"\$+", "", text)
        return re.sub(r"\s+", " ", text).strip() or "未命名标题"

    def _protect_inline_math(self, text: str) -> tuple[str, list[str]]:
        tokens: list[str] = []

        def protect(match: re.Match[str]) -> str:
            token = f"@@MATH_TOKEN_{len(tokens)}@@"
            tokens.append(match.group(0))
            return token

        protected = re.sub(r"\$\$(?:\\.|[^$]|\$(?!\$))*?\$\$", protect, text)
        protected = re.sub(r"\$(?!\$)(?:\\.|[^$\\])*?\$", protect, protected)
        return protected, tokens

    def _render_inline_html(self, text: str) -> str:
        protected, math_tokens = self._protect_inline_math(text)
        escaped = html.escape(protected)
        escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
        escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>', escaped)
        for index, original in enumerate(math_tokens):
            escaped = escaped.replace(f"@@MATH_TOKEN_{index}@@", html.escape(original))
        return escaped

