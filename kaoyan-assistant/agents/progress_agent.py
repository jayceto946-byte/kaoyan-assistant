"""进度追踪Agent - 分析学习状态并给出建议"""
from config import get_llm
from memory.study_memory import StudyMemory

ANALYSIS_PROMPT = """你是一个考研学习规划师。根据以下学习数据，分析用户的学习状态并提供建议。

## 学习数据
{stats}

## 薄弱章节
{weaknesses}

## 最近问答记录
{recent_chats}

## 输出要求
1. 学习状态评估（掌握程度、复习进度）
2. 薄弱环节分析
3. 针对性复习建议
4. 下一阶段学习计划
5. 保持动力的小技巧
"""


class ProgressAgent:
    """进度分析Agent"""

    def __init__(self, study_memory: StudyMemory):
        self.memory = study_memory
        self.llm = get_llm(temperature=0.3)

    def get_analysis(self) -> str:
        """获取学习状态分析报告"""
        stats = self.memory.get_stats()
        weaknesses = self.memory.get_weakness()
        recent = self.memory._chat_history[-20:] if self.memory._chat_history else []

        weakness_str = "\n".join(f"- {w}" for w in weaknesses) if weaknesses else "暂无"
        recent_str = "\n".join(
            f"[{c['chapter']}] {c['role']}: {c['content'][:100]}"
            for c in recent[-5:]
        ) if recent else "暂无"

        stats_str = (
            f"已学章节：{stats['chapters_studied']}个\n"
            f"做题总数：{stats['total_quiz']}道\n"
            f"正确率：{stats['accuracy']}%\n"
            f"薄弱区域：{stats['weak_areas']}处\n"
            f"连续学习：{stats['streak']}天"
        )

        prompt = ANALYSIS_PROMPT.format(
            stats=stats_str,
            weaknesses=weakness_str,
            recent_chats=recent_str,
        )

        result = self.llm.invoke(prompt)
        return result.content

    def recommend_study_plan(self) -> str:
        """推荐学习计划"""
        weaknesses = self.memory.get_weakness()
        progress = self.memory.get_all_progress()

        studied = list(progress.keys())
        weak_str = "、".join(weaknesses[:5]) if weaknesses else "暂无"
        studied_str = "、".join(studied[-5:]) if studied else "暂无"

        prompt = (
            f"你是一个考研学习计划规划师。\n"
            f"用户已学章节：{studied_str}\n"
            f"薄弱章节：{weak_str}\n"
            f"请制定一个接下来3天的学习计划，包括每天的学习目标、复习内容和练习题量。"
            f"要求具体可行，针对薄弱环节。"
        )

        result = self.llm.invoke(prompt)
        return result.content
