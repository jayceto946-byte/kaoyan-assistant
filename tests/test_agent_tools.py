from backend.api.agent import ReadOnlyAgentRequest, _select_tool_calls
from backend.tools.registry import ToolContext, get_tool_registry


def test_tool_registry_exposes_read_only_learning_tools():
    registry = get_tool_registry()
    names = {tool["name"] for tool in registry.list_tools()}

    assert "search_textbook" in names
    assert "search_concepts" in names
    assert "get_due_mistakes" in names
    assert "build_review_plan" in names
    assert "propose_add_mistake" in names


def test_propose_add_mistake_returns_pending_action_without_write():
    registry = get_tool_registry()
    result = registry.call(
        "propose_add_mistake",
        {"question_text": "test question", "user_answer": "A"},
        ToolContext(book_name="default", subject="math"),
    )

    assert result.success is True
    assert result.pending_action is not None
    assert result.pending_action["type"] == "add_mistake"
    assert result.pending_action["payload"]["question_text"] == "test question"


def test_read_only_agent_selects_review_tools_for_review_question():
    req = ReadOnlyAgentRequest(question="我最近有哪些错题到期复习？", book_name="default", subject="math")
    selected = _select_tool_calls(req)
    names = [call["tool"] for call in selected]

    assert "build_review_plan" in names
    assert "get_due_mistakes" in names
    assert "get_mistake_stats" in names
