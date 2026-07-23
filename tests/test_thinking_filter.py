import pytest

from utils.thinking_filter import ThinkingFilter, strip_thinking


def _stream(parts: list[str]) -> str:
    thinking_filter = ThinkingFilter()
    return "".join(thinking_filter.filter(part) for part in parts) + thinking_filter.flush()


@pytest.mark.parametrize("split", range(1, len("<think>")))
def test_split_opening_tag_never_leaks_thinking(split):
    text = "before<think>private reasoning</think>after"
    boundary = len("before") + split
    assert _stream([text[:boundary], text[boundary:]]) == "beforeafter"


@pytest.mark.parametrize("split", range(1, len("</think>")))
def test_split_closing_tag_preserves_answer(split):
    text = "<think>private reasoning</think>answer"
    boundary = len("<think>private reasoning") + split
    assert _stream([text[:boundary], text[boundary:]]) == "answer"


def test_unclosed_thinking_is_discarded_safely():
    assert _stream(["visible<think>private"]) == "visible"
    assert strip_thinking("visible<THINK>private") == "visible"


def test_multiple_thinking_blocks_and_tag_case_are_filtered():
    assert _stream(["a<TH", "INK>one</TH", "INK>b<think>two</think>c"]) == "abc"
