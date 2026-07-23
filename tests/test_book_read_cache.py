import json

from backend.services.book_read_cache import BookReadCache


def test_json_cache_reuses_read_only_snapshot(tmp_path, monkeypatch):
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps({"subject": "数学"}), encoding="utf-8")
    calls = 0
    original = type(path).read_text

    def counted_read_text(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(type(path), "read_text", counted_read_text)
    cache = BookReadCache()

    first = cache.read_json(path, {})
    second = cache.read_json(path, {})

    assert calls == 1
    assert second is first
    assert second == {"subject": "数学"}


def test_json_cache_refreshes_when_file_signature_changes(tmp_path):
    path = tmp_path / "chapters.json"
    path.write_text('[{"title":"第一章"}]', encoding="utf-8")
    cache = BookReadCache()
    assert cache.read_json(path, []) == [{"title": "第一章"}]

    path.write_text('[{"title":"第二章","extra":"changes-size"}]', encoding="utf-8")

    assert cache.read_json(path, []) == [{"title": "第二章", "extra": "changes-size"}]


def test_index_stats_loader_runs_once_per_file_snapshot(tmp_path):
    chapter_map = tmp_path / "_chapter_map.json"
    lexical = tmp_path / "book.json"
    chapter_map.write_text("{}", encoding="utf-8")
    lexical.write_text("[]", encoding="utf-8")
    cache = BookReadCache()
    calls = 0

    def loader():
        nonlocal calls
        calls += 1
        return {"healthy": True, "calls": calls}

    assert cache.index_stats("book", chapter_map, lexical, loader)["calls"] == 1
    assert cache.index_stats("book", chapter_map, lexical, loader)["calls"] == 1
    lexical.write_text('[{"id":1}]', encoding="utf-8")
    assert cache.index_stats("book", chapter_map, lexical, loader)["calls"] == 2
