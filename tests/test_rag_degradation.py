class DummyChunk:
    def __init__(self, content: str):
        self.content = content


class DummyLLM:
    def stream(self, prompt: str):
        yield DummyChunk("answer")


class EmptyVectorStore:
    available = True

    def get_chapter_names(self):
        return []

    def search_all(self, *args, **kwargs):
        return {}

    def search_chapter(self, *args, **kwargs):
        return []


def _use_fast_path(monkeypatch):
    import config
    import graph.feedback_node as feedback_module
    import graph.intent_classifier as intent_module

    monkeypatch.setattr(intent_module, "classify_intent_local", lambda text: {"intent": "definition", "hint": "local"})
    monkeypatch.setattr(intent_module, "is_fast_path_eligible", lambda text, result: True)
    monkeypatch.setattr(config, "get_llm", lambda: DummyLLM())
    monkeypatch.setattr(feedback_module, "feedback_node", lambda state: {})


def _assert_degraded_stream(events, expected_error: str):
    stages = [event["stage"] for event in events]
    assert stages[0] == "plan"
    assert stages[1] == "retrieve"
    assert "generate" in stages
    assert stages[-1] == "done"
    retrieve = events[1]
    assert retrieve["retrieval_status"] == "degraded"
    assert expected_error in retrieve["retrieval_error"]


def test_stream_degrades_when_vector_store_initialization_fails(monkeypatch):
    import ingestion.vector_store as vector_module
    import graph.retrieval_node as retrieval_module
    import graph.safe_retrieval as safe_retrieval
    from graph.main_graph import run_graph_stream

    _use_fast_path(monkeypatch)
    monkeypatch.setattr(vector_module, "get_vector_store", lambda: (_ for _ in ()).throw(RuntimeError("vector boom")))
    monkeypatch.setattr(retrieval_module, "get_safe_kg", lambda book_name: (safe_retrieval.SafeKG(), ""))

    events = list(run_graph_stream("what is derivative", book_name="demo-book"))

    _assert_degraded_stream(events, "vector boom")


def test_stream_degrades_when_kg_loading_fails(monkeypatch):
    import ingestion.vector_store as vector_module
    import knowledge.knowledge_graph as kg_module
    from graph.main_graph import run_graph_stream

    _use_fast_path(monkeypatch)
    monkeypatch.setattr(vector_module, "get_vector_store", lambda: EmptyVectorStore())
    monkeypatch.setattr(kg_module, "get_kg", lambda book_name: (_ for _ in ()).throw(ValueError("kg json corrupt")))

    events = list(run_graph_stream("what is derivative", book_name="demo-book"))

    _assert_degraded_stream(events, "kg json corrupt")