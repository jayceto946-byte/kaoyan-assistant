def test_automatic_feedback_never_calls_llm_concept_extractor(monkeypatch):
    import graph.feedback_node as feedback
    import knowledge.concept_memory as concept_memory
    import memory.learning_events as learning_events

    extractor_calls = []

    class DummyMemory:
        def __init__(self, book_name: str):
            self.book_name = book_name

        def extract_concepts(self, question: str, answer: str):
            extractor_calls.append((question, answer))
            return []

    class DummyStore:
        def append(self, event):
            return event.id

    monkeypatch.setattr(feedback, "_link_concepts_locally", lambda state: [])
    monkeypatch.setattr(concept_memory, "ConceptMemory", DummyMemory)
    monkeypatch.setattr(learning_events, "get_learning_event_store", lambda: DummyStore())

    result = feedback._record_concept_memory(
        {
            "book_name": "demo",
            "user_input": "question",
            "final_output": "answer",
            "intent": "qa",
        }
    )

    assert result == []
    assert extractor_calls == []


def test_response_concept_linking_is_local_and_strict(monkeypatch):
    import graph.feedback_node as feedback

    monkeypatch.setattr(
        feedback,
        "_link_concepts_locally",
        lambda state: [
            {"name": "梯度", "confidence": 1.0, "aliases": []},
            {"name": "直接命中", "confidence": 0.88, "aliases": []},
            {"name": "候选词", "confidence": 0.8, "aliases": []},
        ],
    )

    assert feedback.link_concepts_for_response({"user_input": "什么是梯度和直接命中"}) == [
        {"name": "梯度", "confidence": 1.0, "aliases": []},
        {"name": "直接命中", "confidence": 0.88, "aliases": []},
    ]

def test_feedback_node_survives_learning_storage_failure(monkeypatch):
    import graph.feedback_node as feedback

    def fail_feedback(state):
        raise RuntimeError("disk failure")

    monkeypatch.setattr(feedback, "_feedback_node_impl", fail_feedback)
    monkeypatch.setattr(feedback, "link_concepts_for_response", lambda state: [])

    result = feedback.feedback_node({"final_output": "answer"})

    assert result["linked_concepts"] == []
    assert result["mastery_update"] == {}

def test_generic_qa_extracts_only_direct_high_confidence_concepts(monkeypatch):
    import graph.feedback_node as feedback
    import knowledge.concept_memory as concept_memory
    import memory.learning_events as learning_events

    captured = {"events": [], "exposures": [], "candidates": [], "books": []}

    class DummyMemory:
        def __init__(self, book_name: str):
            captured["books"].append(book_name)

        def extract_concepts(self, question: str, answer: str):
            return [
                {"name": "导数", "confidence": 0.95, "aliases": []},
                {"name": "极限", "confidence": 0.99, "aliases": []},
                {"name": "求导", "confidence": 0.7, "aliases": []},
            ]

        def log_exposure(self, concepts, question, intent, **kwargs):
            captured["exposures"].append((concepts, question, intent, kwargs))

        def log_candidates(self, concepts, question, intent, **kwargs):
            captured["candidates"].append((concepts, question, intent, kwargs))

    class DummyStore:
        def append(self, event):
            captured["events"].append(event)
            return event.id

    monkeypatch.setattr(feedback, "_link_concepts_locally", lambda state: [])
    monkeypatch.setattr(concept_memory, "ConceptMemory", DummyMemory)
    monkeypatch.setattr(learning_events, "get_learning_event_store", lambda: DummyStore())

    result = feedback._record_concept_memory(
        {
            "book_name": "",
            "subject": "数学/高数",
            "conversation_id": "conv-generic",
            "user_input": "导数怎么求",
            "final_output": "可以先用导数定义，再选择求导法则。",
            "intent": "qa",
        }
    )

    assert captured["books"] == ["default"]
    assert [item["name"] for item in result] == ["导数"]
    assert [item["name"] for item in captured["exposures"][0][0]] == ["导数"]
    assert {item["name"] for item in captured["candidates"][0][0]} == {"极限", "求导"}
    chat_event = next(event for event in captured["events"] if event.event_type == "chat_qa")
    assert chat_event.book_name == "default"
    assert chat_event.payload["question"] == "导数怎么求"
    assert chat_event.concept_names == ["导数"]
