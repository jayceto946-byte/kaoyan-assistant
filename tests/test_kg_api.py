import json

from fastapi.testclient import TestClient

from backend.main import app


class DummyKG:
    def __init__(self, graph):
        self._graph = graph
        self.called = False

    def graph(self):
        self.called = True
        return self._graph


def test_kg_graph_counts_concepts_from_graph_method(monkeypatch, tmp_path):
    from backend.api import kg as kg_api
    import knowledge.knowledge_graph as kg_module

    book_name = "demo-book"
    progress_root = tmp_path / "progress"
    html_dir = progress_root / book_name
    html_dir.mkdir(parents=True)
    (html_dir / "kg_graph.html").write_text("<html>cached</html>", encoding="utf-8")

    dummy = DummyKG({"concept-a": {"chapter": "chapter-1"}})
    monkeypatch.setattr(kg_api, "PROGRESS_PATH", progress_root)
    monkeypatch.setattr(kg_module, "get_kg", lambda name: dummy)

    client = TestClient(app)
    data = client.get("/api/kg/graph", params={"book_name": book_name}).json()

    assert data["exists"] is True
    assert data["html_content"] == "<html>cached</html>"
    assert data["concept_count"] == 1
    assert dummy.called is True


def test_kg_refresh_uses_graph_method(monkeypatch, tmp_path):
    from backend.api import kg as kg_api
    import knowledge.knowledge_graph as kg_module
    import knowledge.kg_visualizer as viz_module

    graph = {"concept-a": {"chapter": "chapter-1"}}
    dummy = DummyKG(graph)
    monkeypatch.setattr(kg_api, "PROGRESS_PATH", tmp_path / "progress")
    monkeypatch.setattr(kg_module, "get_kg", lambda name: dummy)

    class DummyVisualizer:
        def __init__(self, book_name):
            self.book_name = book_name

        def enrich_definitions(self, received_graph, vector_store=None):
            assert received_graph == graph
            assert vector_store is None
            return {"concept-a": "definition"}, {}

        def generate_html(self, received_graph, definitions, kg_instance=None):
            assert received_graph == graph
            assert definitions == {"concept-a": "definition"}
            assert kg_instance is dummy
            return "<html>fresh</html>"

        def save_html(self, html):
            assert html == "<html>fresh</html>"
            return "unused"

    monkeypatch.setattr(viz_module, "KGVisualizer", DummyVisualizer)

    client = TestClient(app)
    data = client.post("/api/kg/refresh", params={"book_name": "demo-book"}).json()

    assert data["success"] is True
    assert data["html_content"] == "<html>fresh</html>"
    assert data["concept_count"] == 1
    assert dummy.called is True


def test_kg_visualizer_load_kg_uses_graph_method(monkeypatch):
    import knowledge.knowledge_graph as kg_module
    from knowledge.kg_visualizer import KGVisualizer

    graph = {"concept-a": {"chapter": "chapter-1"}}
    dummy = DummyKG(graph)
    monkeypatch.setattr(kg_module, "get_kg", lambda name: dummy)

    assert KGVisualizer("demo-book").load_kg() == graph
    assert dummy.called is True


def test_knowledge_graph_prefers_configured_mineru_output(monkeypatch, tmp_path):
    import knowledge.knowledge_graph as kg_module

    book_name = "demo-book"
    mineru_root = tmp_path / "configured-mineru"
    local_dir = mineru_root / book_name / "hybrid_auto"
    local_dir.mkdir(parents=True)
    kg_file = local_dir / f"{book_name}_knowledge_graph.json"
    kg_file.write_text(
        json.dumps(
            {
                "meta": {},
                "concepts": [
                    {
                        "concept_id": "c1",
                        "canonical_name": "concept-a",
                        "aliases": [],
                        "confidence": 1.0,
                        "occurrence_count": 0,
                        "roles": [],
                    }
                ],
                "formulas": [],
                "occurrences": [],
                "relations": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(kg_module, "MINERU_OUTPUT_PATH", mineru_root)
    monkeypatch.setattr(kg_module, "BASE_DIR", tmp_path / "legacy-base")

    kg = kg_module.KnowledgeGraph(book_name)

    assert kg.file == kg_file
    assert kg.graph()["concept-a"]["_concept_id"] == "c1"