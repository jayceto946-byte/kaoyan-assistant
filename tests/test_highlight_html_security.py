from knowledge.chapter_highlights import ChapterHighlightService


def test_highlight_links_reject_executable_schemes():
    service = ChapterHighlightService()

    assert service._safe_link_url("javascript:alert(1)") == ""
    assert service._safe_link_url("data:text/html,unsafe") == ""
    assert service._safe_link_url("file:///C:/secret.txt") == ""
    assert service._safe_link_url("//example.com/path") == ""
    assert service._safe_link_url("https://example.com/reference") == "https://example.com/reference"
    assert service._safe_link_url("/api/books/demo") == "/api/books/demo"

    rendered = service._render_inline_html("[unsafe](javascript:alert)")
    assert "javascript:" not in rendered
    assert "<a " not in rendered


def test_highlight_html_includes_restrictive_csp():
    service = ChapterHighlightService()
    html = service._build_highlight_html(
        "demo",
        "# Title",
        {"scope": {"title": "Title"}},
        {"updated_at": "2026-07-10"},
    )

    assert "Content-Security-Policy" in html
    assert "object-src 'none'" in html
    assert "connect-src 'none'" in html
