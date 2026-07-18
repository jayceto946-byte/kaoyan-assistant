import json


def test_mineru_native_chunk_metadata_is_preserved():
    from ingestion.mineru_importer import _chapters_from_content_list
    from ingestion.textbook_chunk import TextbookChunk

    chapters = _chapters_from_content_list(
        [{
            "type": "text", "text": "Definition of sensor sensitivity", "page_idx": 6,
            "bbox": [1, 2, 30, 40], "semantic_role": "definition",
            "equations": ["S=dy/dx"], "source_markdown": "page_7.md",
        }],
        "demo",
    )
    source = chapters[0]["chunks"][0]
    chunk = TextbookChunk.from_source(source, book_name="demo", chapter=chapters[0]["title"], chunk_index=0)
    assert chunk is not None
    assert chunk.page_idx == 6
    assert chunk.bbox == [1.0, 2.0, 30.0, 40.0]
    assert chunk.role == "definition"
    assert chunk.equations == ["S=dy/dx"]
    assert chunk.source_markdown == "page_7.md"


def test_build_index_updates_aggregate(monkeypatch, tmp_path):
    from ingestion import mineru_importer

    captured = {"chapters": [], "aggregate": []}

    class FakeVectorStore:
        def build_chapter_store(self, title, chunks, chunk_roles=None, book_name=""):
            captured["chapters"].append((title, chunks, book_name))

        def build_book_aggregate_store(self, book_name, chunks):
            captured["aggregate"].append((book_name, chunks))

        def get_book_index_stats(self, book_name):
            count = sum(len(item[1]) for item in captured["chapters"])
            return {"healthy": count > 0, "chunk_count": count}

    monkeypatch.setattr(mineru_importer, "get_vector_store", lambda: FakeVectorStore())
    monkeypatch.setattr(mineru_importer, "write_book_index", lambda *args, **kwargs: None)
    monkeypatch.setattr(mineru_importer, "load_kg_chunk_roles", lambda book_name: {})
    count = mineru_importer.build_index_from_chapters(
        "demo",
        [{"title": "chapter", "text": "Definition text", "page_number": 1}],
        tmp_path,
    )
    assert count > 0
    assert len(captured["aggregate"]) == 1
    assert len(captured["aggregate"][0][1]) == count


def test_user_kg_graph_contains_no_directional_relations():
    from knowledge.kg_enhancement import build_evidence_graph

    chunks = [{"chunk_id": "c1", "content": "Sensitivity is output change over input change."}]
    candidates = [{
        "chunk_id": "c1", "chapter": "chapter", "section_title": "definition",
        "page_idx": 2, "role": "definition",
        "concepts": [{"name": "Sensitivity", "aliases": [], "definition": "Sensitivity is output change over input change.", "formulas": ["S=dy/dx"]}],
    }]
    graph = build_evidence_graph("demo", chunks, candidates)
    assert graph["relations"] == []
    assert graph["concepts"][0]["occurrences"][0]["chunk_id"] == "c1"
    assert graph["formulas"][0]["related_concepts"] == [graph["concepts"][0]["concept_id"]]


def test_resource_group_is_driven_by_metadata(monkeypatch, tmp_path):
    from utils import resource_groups

    progress = tmp_path / "progress"
    for name, role, priority in [("main-book", "core", 1.0), ("reference-book", "reference", 0.4)]:
        folder = progress / name
        folder.mkdir(parents=True)
        (folder / "metadata.json").write_text(
            json.dumps({"subject": "course-a", "book_role": role, "rag_priority": priority}),
            encoding="utf-8",
        )
    monkeypatch.setattr(resource_groups, "PROGRESS_PATH", progress)
    resources = resource_groups.resolve_retrieval_resources("reference-book", "course-a")
    assert [item["book_name"] for item in resources] == ["main-book", "reference-book"]
    assert resources[0]["is_primary"] is True
    assert resources[1]["role"] == "reference"
    assert resources[1]["priority"] == 0.4


def test_generator_does_not_include_directional_kg_path():
    from graph.generator import _build_generate_prompt

    prompt = _build_generate_prompt({
        "intent": "definition", "user_input": "question", "use_textbook_context": True,
        "chapter_contents": {"chapter": ["evidence text"]},
        "evidence_items": [{"chapter": "chapter", "section_title": "section", "page_idx": 0, "text": "evidence text"}],
        "concept_results": [], "history_results": [], "teaching_content": "",
        "knowledge_graph_path": ["UNTRUSTED_DIRECTIONAL_EDGE"],
    })
    assert "UNTRUSTED_DIRECTIONAL_EDGE" not in prompt
