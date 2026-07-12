"""Regression tests for non-destructive subject catalog updates."""
from backend.api import system


def test_save_subjects_rejects_orphaned_book_assignments(monkeypatch):
    written = []
    monkeypatch.setattr(system, "_subject_values_in_use", lambda: ["数学/高数"])
    monkeypatch.setattr(system, "_write_subject_tree", lambda tree: written.append(tree) or tree)

    result = system.save_subjects({"subjects": [{"name": "数学", "children": ["线代"]}]})

    assert result["success"] is False
    assert "数学/高数" in result["message"]
    assert written == []


def test_save_subjects_accepts_catalog_that_keeps_assignments(monkeypatch):
    monkeypatch.setattr(system, "_subject_values_in_use", lambda: ["数学/高数", "专业课"])
    monkeypatch.setattr(system, "_write_subject_tree", lambda tree: tree)

    result = system.save_subjects({
        "subjects": [
            {"name": "数学", "children": ["高数", "线代"]},
            {"name": "专业课", "children": []},
        ]
    })

    assert result["success"] is True
    assert result["data"][0]["children"] == ["高数", "线代"]
