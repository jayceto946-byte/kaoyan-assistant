from backend.services.book_chapters import (
    chapters_from_embedded_toc,
    chapters_from_ocr_headings,
    format_chapter,
    looks_like_external_ocr_chunk_titles,
)


def test_external_ocr_shape_detection_keeps_existing_thresholds():
    chapters = [
        {
            "title": f"片段 {index}",
            "source": "external_ocr_jsonl" if index < 20 else "",
            "chunk_count": 1,
        }
        for index in range(80)
    ]
    assert looks_like_external_ocr_chunk_titles(chapters) is True
    assert looks_like_external_ocr_chunk_titles(chapters[:79]) is False


def test_ocr_heading_fallback_builds_chapters_and_sections():
    chapters = [
        {"title": "第一章 绪论", "page_number": 1},
        {"title": "第一节 背景", "page_number": 2},
        {"title": "第二章 方法", "page_number": 10},
    ]
    result = chapters_from_ocr_headings(chapters)
    assert [item["title"] for item in result] == ["第一章 绪论", "第二章 方法"]
    assert result[0]["subsections"] == [{"title": "第一节 背景", "page": 2}]


def test_embedded_toc_preserves_page_ranges_and_output_shape():
    chapters = [{
        "title": "目录",
        "text": "目录\n第一章 绪论 ...... 1\n第一节 背景 ...... 2\n第二章 方法 ...... 10",
    }]
    result = chapters_from_embedded_toc(chapters)
    assert result[0]["end_page"] == 9
    assert format_chapter(result[0]) == {
        "title": "第一章 绪论",
        "page": 1,
        "end_page": 9,
        "subsections": [{"title": "第一节 背景", "page": 2, "end_page": None}],
    }
