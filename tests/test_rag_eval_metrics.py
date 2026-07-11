from scripts.evaluate_rag import EvalSample, retrieval_metrics


def test_retrieval_metrics_use_gold_chunks_for_recall_and_flag_forbidden():
    sample = EvalSample(
        question="q",
        expected_chunk_ids=["gold-a", "gold-b"],
        forbidden_chunk_ids=["toc"],
        expected_pages=[12],
    )
    candidates = [
        {"chunk_id": "toc", "page_idx": 1},
        {"chunk_id": "gold-a", "page_idx": 12},
        {"chunk_id": "gold-b", "page_idx": 13},
    ]

    metrics = retrieval_metrics(sample, candidates, [1, 2, 3])
    assert metrics["hit@1"] == 0.0
    assert metrics["recall@2"] == 0.5
    assert metrics["recall@3"] == 1.0
    assert metrics["mrr"] == 0.5
    assert metrics["forbidden_hits"] == ["toc"]
    assert metrics["page_hit"] is True
