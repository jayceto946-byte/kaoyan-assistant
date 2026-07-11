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
            {"name": "候选词", "confidence": 0.8, "aliases": []},
        ],
    )

    assert feedback.link_concepts_for_response({"user_input": "什么是梯度"}) == [
        {"name": "梯度", "confidence": 1.0, "aliases": []}
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
