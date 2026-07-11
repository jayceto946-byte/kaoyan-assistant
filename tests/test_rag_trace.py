import backend.rag_trace as trace


def test_rag_trace_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(trace, "TRACE_DB_PATH", tmp_path / "traces.db")
    trace.save_trace({
        "request_id": "req-1",
        "book_name": "demo",
        "question": "what is x",
        "intent": "definition",
        "fast_path": True,
        "status": "done",
        "ttft_ms": 120.5,
        "total_ms": 300.0,
        "timings": {"retrieve": 50.0},
        "evidence": [{"chunk_id": "c1", "chapter": "one", "text": "must not persist"}],
    })

    rows = trace.list_traces()
    assert rows[0]["request_id"] == "req-1"
    assert rows[0]["fast_path"] is True
    assert rows[0]["timings"]["retrieve"] == 50.0
    assert rows[0]["evidence"] == [{
        "chunk_id": "c1", "chapter": "one", "section_title": "", "source": "", "score": None,
    }]

