from backend.api import kg


def test_learning_summary_cache_reuses_result_until_dependency_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(kg, "PROGRESS_PATH", tmp_path)
    kg._learning_summary_cache.clear()
    calls = 0

    def compute(book_name="", subject="", limit=30):
        nonlocal calls
        calls += 1
        return {"success": True, "data": {"calls": calls}}

    monkeypatch.setattr(kg, "_compute_learning_summary", compute)

    first = kg.get_learning_summary("demo", "数学", 30)
    second = kg.get_learning_summary("demo", "数学", 30)
    assert first == second == {"success": True, "data": {"calls": 1}}

    concept_file = tmp_path / "demo" / "concept_memory.json"
    concept_file.parent.mkdir(parents=True)
    concept_file.write_text("{}", encoding="utf-8")
    refreshed = kg.get_learning_summary("demo", "数学", 30)
    assert refreshed["data"]["calls"] == 2


def test_learning_summary_failures_are_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(kg, "PROGRESS_PATH", tmp_path)
    kg._learning_summary_cache.clear()
    calls = 0

    def compute(*_args):
        nonlocal calls
        calls += 1
        return {"success": False, "data": None, "calls": calls}

    monkeypatch.setattr(kg, "_compute_learning_summary", compute)
    kg.get_learning_summary("demo")
    second = kg.get_learning_summary("demo")
    assert second["calls"] == 2
