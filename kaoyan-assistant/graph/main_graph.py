"""LangGraph 主图 — 总调度器，串联 Planner → Retrieval → Chapter → Generator → Feedback"""
from langgraph.graph import StateGraph, START, END
from graph.state import AgentState
from graph.planner import plan_node
from graph.retrieval_node import retrieve_node
from graph.chapter_subgraph import chapter_subgraph_run
from graph.generator import generate_node
from graph.feedback_node import feedback_node


def build_main_graph() -> StateGraph:
    """构建考研学习主图

    流程:
      START → plan → retrieve → chapter → generate → feedback → END
    """
    graph = StateGraph(AgentState)

    # 注册节点
    graph.add_node("plan", plan_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("chapter", chapter_subgraph_run)
    graph.add_node("generate", generate_node)
    graph.add_node("feedback", feedback_node)

    # 定义边
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "retrieve")
    graph.add_edge("retrieve", "chapter")
    graph.add_edge("chapter", "generate")
    graph.add_edge("generate", "feedback")
    graph.add_edge("feedback", END)

    return graph.compile()


# 全局编译好的图实例（单例）
_main_graph = None


def get_graph() -> StateGraph:
    global _main_graph
    if _main_graph is None:
        _main_graph = build_main_graph()
    return _main_graph


def run_graph(user_input: str, book_name: str = "default",
              user_images: list[str] = None,
              user_feedback: dict = None) -> dict:
    """运行一次完整的图谱推理

    Args:
        user_input: 用户输入的问题/指令
        book_name: 当前教材名
        user_images: 多模态图片路径
        user_feedback: 用户反馈（评分等）

    Returns:
        最终状态字典
    """
    graph = get_graph()

    initial_state = {
        "user_input": user_input,
        "user_images": user_images or [],
        "user_profile": {},
        "learning_progress": {},
        "long_term_memory": {},
        "book_name": book_name,
        "messages": [],
        "intent": "",
        "sub_tasks": [],
        "target_chapters": [],
        "route_decision": "",
        "chapter_contents": {},
        "concept_results": [],
        "history_results": [],
        "knowledge_graph_path": [],
        "teaching_content": "",
        "key_points": [],
        "extracted_examples": [],
        "quiz_questions": [],
        "chapter_summary": "",
        "final_output": "",
        "output_type": "text",
        "user_feedback": user_feedback,
        "mastery_update": {},
        "next_review": None,
        "error": "",
        "iteration": 0,
        "max_iterations": 10,
    }

    result = graph.invoke(initial_state)
    return result
