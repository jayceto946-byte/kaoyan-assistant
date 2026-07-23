from backend.services.dependency_cache import DependencyTTLCache


def test_dependency_cache_reuses_value_and_returns_copy(tmp_path):
    now = [10.0]
    dependency = tmp_path / "state.json"
    dependency.write_text("{}", encoding="utf-8")
    cache = DependencyTTLCache(5, clock=lambda: now[0])
    calls = 0

    def factory():
        nonlocal calls
        calls += 1
        return {"calls": calls}

    first = cache.get_or_compute("summary", [dependency], factory)
    first["calls"] = 99
    assert cache.get_or_compute("summary", [dependency], factory) == {"calls": 1}
    assert calls == 1


def test_dependency_change_and_ttl_expiry_force_refresh(tmp_path):
    now = [10.0]
    dependency = tmp_path / "state.json"
    dependency.write_text("{}", encoding="utf-8")
    cache = DependencyTTLCache(5, clock=lambda: now[0])
    calls = 0

    def factory():
        nonlocal calls
        calls += 1
        return calls

    assert cache.get_or_compute("summary", [dependency], factory) == 1
    dependency.write_text('{"changed":true}', encoding="utf-8")
    assert cache.get_or_compute("summary", [dependency], factory) == 2
    now[0] = 16.0
    assert cache.get_or_compute("summary", [dependency], factory) == 3


def test_failed_result_can_be_excluded_from_cache():
    cache = DependencyTTLCache(5)
    calls = 0

    def factory():
        nonlocal calls
        calls += 1
        return {"success": False, "calls": calls}

    predicate = lambda value: bool(value.get("success"))
    cache.get_or_compute("summary", [], factory, should_cache=predicate)
    result = cache.get_or_compute("summary", [], factory, should_cache=predicate)
    assert result["calls"] == 2
