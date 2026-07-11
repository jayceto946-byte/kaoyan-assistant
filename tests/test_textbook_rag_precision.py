from evaluation.rag_eval import aggregate, score_case
from graph.generator import grounded_failure_message
from graph.intent_classifier import classify_intent_local
from graph.retrieval_node import _merge_and_rerank
from ingestion.chapter_splitter import ChapterSplitter


def test_factual_recall_intent_for_reason_question():
    result = classify_intent_local("\u7535\u5bb9\u5f0f\u4f20\u611f\u5668\u662f\u5426\u9002\u5408\u52a8\u6001\u6d4b\u91cf\uff1f\u4e3a\u4ec0\u4e48\uff1f")
    assert result["intent"] == "factual_recall"


def test_structure_aware_chunks_keep_context_and_neighbors():
    splitter = ChapterSplitter(chunk_size=80, chunk_overlap=10)
    rows = splitter.split_chapter(
        "chapter 4",
        "## 4.3 capacitor\n\n### dynamic response\nsmall force, low mass, low dielectric loss.",
        book_name="sensors",
    )
    assert rows
    assert rows[0]["section_path"][0] == "chapter 4"
    assert "sensors" in rows[0]["retrieval_text"]
    if len(rows) > 1:
        assert rows[0]["next_chunk_id"] == rows[1]["chunk_id"]


def test_rrf_fusion_promotes_chunk_found_by_dense_and_bm25():
    common = {
        "chapter": "c", "chunk_id": "gold", "text": "capacitor dynamic response low mass",
        "source": "vector", "retrieval_rank": 4, "role": "property",
    }
    lexical = dict(common, source="bm25", retrieval_rank=1)
    distractor = {
        "chapter": "c", "chunk_id": "distractor", "text": "general sensor introduction",
        "source": "vector", "retrieval_rank": 1, "role": "definition",
    }
    _, debug = _merge_and_rerank(
        [], [common, lexical, distractor], query="capacitor dynamic response",
        intent="factual_recall", include_metadata=True,
    )
    assert debug[0]["chunk_id"] == "gold"
    assert set(debug[0]["fusion_sources"]) == {"dense", "bm25"}


def test_point_completeness_requires_all_parallel_points():
    case = {
        "id": "dynamic", "answerable": True,
        "required_points": ["small force", "low mass", "low loss"],
    }
    partial = score_case(case, [{"text": "low mass"}], k=5)
    complete = score_case(case, [{"text": "small force; low mass; low loss"}], k=5)
    assert partial["recall_at_k"] == 0
    assert partial["point_recall"] == 1 / 3
    assert complete["recall_at_k"] == 1
    assert complete["reciprocal_rank"] == 1


def test_aggregate_metrics():
    report = aggregate([
        {"recall_at_k": 1.0, "reciprocal_rank": 1.0, "point_recall": 1.0},
        {"recall_at_k": 0.0, "reciprocal_rank": 0.0, "point_recall": 0.5},
    ])
    assert report == {"cases": 2, "recall_at_k": 0.5, "mrr": 0.5, "point_recall": 0.75}


def test_empty_book_index_message_disallows_model_fallback():
    message = grounded_failure_message({"retrieval_error": "book_index_empty"})
    assert "\u6a21\u578b\u81ea\u8eab\u77e5\u8bc6" in message
    assert "\u91cd\u5efa" in message
