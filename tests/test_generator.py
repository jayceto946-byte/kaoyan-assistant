"""生成节点相关单元测试"""
from graph.generator import _build_generate_prompt, _has_example_marker


def test_build_prompt_includes_longer_context():
    """教材 chunk 不应被截断到 500 字符，否则例题题干会丢失。"""
    long_content = "例4-4 " + "用梯度法求解例4-2无约束优化问题： " * 20 + "$$x_1^2 + 2x_2^2$$" + " 解：第一次迭代..." * 20
    state = {
        "intent": "definition",
        "user_input": "梯度下降法是什么",
        "chapter_contents": {"第四章 无约束优化方法": [long_content]},
        "concept_results": [],
        "history_results": [],
        "knowledge_graph_path": [],
        "teaching_content": "",
    }
    prompt = _build_generate_prompt(state)
    # 修复后：每个 doc 至少保留 1500 字符，因此完整题干和后续解题步骤都应进入 prompt
    assert "例4-2" in prompt
    assert "$$x_1^2 + 2x_2^2$$" in prompt
    assert " 解：第一次迭代..." * 10 in prompt  # 后半部分解题步骤也应保留


def test_build_prompt_includes_multiple_docs():
    """应使用同章节多个 doc，提升例题完整性。"""
    doc1 = "例4-4 题干部分..."
    doc2 = "...题干继续..."
    doc3 = "...解题步骤..."
    state = {
        "intent": "definition",
        "user_input": "梯度下降法是什么",
        "chapter_contents": {"第四章 无约束优化方法": [doc1, doc2, doc3]},
        "concept_results": [],
        "history_results": [],
        "knowledge_graph_path": [],
        "teaching_content": "",
    }
    prompt = _build_generate_prompt(state)
    assert doc1 in prompt
    assert doc2 in prompt
    assert doc3 in prompt


def test_build_prompt_warns_about_incomplete_examples():
    """prompt 应提醒 LLM 不要基于不完整的例题题干编造。"""
    state = {
        "intent": "definition",
        "user_input": "梯度下降法是什么",
        "chapter_contents": {"第四章 无约束优化方法": ["部分内容"]},
        "concept_results": [],
        "history_results": [],
        "knowledge_graph_path": [],
        "teaching_content": "",
    }
    prompt = _build_generate_prompt(state)
    assert "完整" in prompt or "题干" in prompt or "编造" in prompt or "缺失" in prompt


def test_has_example_marker_detects_examples():
    """_has_example_marker 应能识别各种例题标记格式。"""
    assert _has_example_marker("例4-2 用梯度法求解...") is True
    assert _has_example_marker("例 3.1 证明...") is True
    assert _has_example_marker("例5 求函数极小值...") is True
    assert _has_example_marker("定义：梯度下降法是指...") is False
    assert _has_example_marker("定理1（最优性条件）...") is False
    assert _has_example_marker("") is False


def test_prompt_includes_example_check_when_example_found():
    """检索到例题标记时，prompt 应包含例题完整性自检说明。"""
    state = {
        "intent": "definition",
        "user_input": "梯度下降法是什么",
        "chapter_contents": {"第四章": ["例4-2 用梯度法求解无约束优化问题..."]},
        "concept_results": [],
        "history_results": [],
        "knowledge_graph_path": [],
        "teaching_content": "",
    }
    prompt = _build_generate_prompt(state)
    assert "例题完整性自检" in prompt
    assert "完整题干" in prompt


def test_prompt_uses_fallback_when_no_example():
    """未检索到例题标记时，prompt 应使用允许补充例题的 fallback 约束。"""
    state = {
        "intent": "definition",
        "user_input": "梯度下降法是什么",
        "chapter_contents": {"第四章": ["梯度下降法是一种迭代算法..."]},
        "concept_results": [],
        "history_results": [],
        "knowledge_graph_path": [],
        "teaching_content": "",
    }
    prompt = _build_generate_prompt(state)
    assert "补充例题" in prompt
