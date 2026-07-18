"""Seed an isolated runtime with deterministic, non-personal demo records.

This script deliberately refuses to write to the repository's formal data
directory or to ``desktop/sample_data``. Copy the bundled sample data to a
separate directory first, then pass that directory explicitly with
``--data-dir``.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
FORBIDDEN_ROOTS = (
    (PROJECT_ROOT / "data").resolve(),
    (PROJECT_ROOT / "desktop" / "sample_data").resolve(),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed isolated documentation demo data.")
    parser.add_argument("--data-dir", required=True, help="Explicit path to an isolated data directory")
    parser.add_argument("--book-name", default="优化设计", help="Demo textbook name")
    parser.add_argument("--subject", default="数学", help="Demo subject")
    return parser.parse_args()


def validate_target(raw_path: str) -> Path:
    target = Path(raw_path).expanduser().resolve()
    for forbidden in FORBIDDEN_ROOTS:
        if target == forbidden or forbidden in target.parents:
            raise SystemExit(f"Refusing to seed protected data directory: {target}")
    target.mkdir(parents=True, exist_ok=True)
    return target


def main() -> None:
    args = parse_args()
    data_dir = validate_target(args.data_dir)
    progress_dir = data_dir / "progress"
    progress_dir.mkdir(parents=True, exist_ok=True)

    # Configure paths before importing project modules, because config.py reads
    # environment variables at import time.
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ["PROGRESS_PATH"] = str(progress_dir)
    os.environ["BOOKS_PATH"] = str(data_dir / "books")
    os.environ["CHAPTERS_PATH"] = str(data_dir / "chapters")
    os.environ["IMAGES_PATH"] = str(data_dir / "images")
    os.environ["VECTOR_DB_PATH"] = str(data_dir / "vector_db")
    os.environ["SKIP_EMBEDDING_WARMUP"] = "1"
    os.environ["SKIP_VECTOR_WARMUP"] = "1"

    from backend.conversation_memory import append_message, load_history
    from memory.exercise_bank import ExerciseRecord, get_exercise_bank
    from memory.mistake_book import MistakeRecord, get_mistake_book

    now = datetime.now()
    created_recently = (now - timedelta(days=1)).isoformat(timespec="seconds")
    today = date.today().isoformat()
    book_name = args.book_name.strip()
    subject = args.subject.strip()

    exercises = [
        ExerciseRecord(
            id="demoex01",
            question_text="求函数 $f(x)=x^2-4x+5$ 的极小点与极小值。",
            answer="$x=2$，极小值为 $1$。",
            explanation="配方得 $f(x)=(x-2)^2+1$，因此在 $x=2$ 处取得极小值。",
            source="Demo seed",
            subject=subject,
            chapter="一维搜索基础",
            tags=["极值", "配方法"],
            question_type="计算题",
            difficulty=1,
            linked_concepts=[{"name": "极小值", "confidence": 1.0, "source": "demo"}],
            status="mastered",
            practice_count=2,
            last_practiced=created_recently,
            practice_history=[{"timestamp": created_recently, "quality": 5, "user_answer": "x=2", "note": "演示记录"}],
            created_at=created_recently,
        ),
        ExerciseRecord(
            id="demoex02",
            question_text="用黄金分割法缩短区间 $[0,4]$，写出第一轮的两个试探点。",
            answer=r"$x_1\approx1.528$，$x_2\approx2.472$。",
            explanation=r"取比例 $0.618$：$x_1=4-0.618\times4$，$x_2=0.618\times4$。",
            source="Demo seed",
            subject=subject,
            chapter="一维搜索基础",
            tags=["黄金分割法", "区间搜索"],
            question_type="计算题",
            difficulty=2,
            linked_concepts=[{"name": "黄金分割法", "confidence": 1.0, "source": "demo"}],
            status="practicing",
            practice_count=1,
            last_practiced=created_recently,
            practice_history=[{"timestamp": created_recently, "quality": 3, "user_answer": "", "note": "演示记录"}],
            created_at=created_recently,
        ),
        ExerciseRecord(
            id="demoex03",
            question_text="判断点 $x^{(k)}$ 是否满足无约束优化的一阶必要条件，应检查什么？",
            answer=r"检查梯度是否为零，即 $\nabla f(x^{(k)})=0$。",
            explanation="可微无约束问题的局部极小点必须是驻点，但驻点未必是极小点。",
            source="Demo seed",
            subject=subject,
            chapter="无约束优化",
            tags=["梯度", "一阶必要条件"],
            question_type="概念题",
            difficulty=2,
            linked_concepts=[{"name": "一阶必要条件", "confidence": 1.0, "source": "demo"}],
            status="needs_review",
            practice_count=1,
            last_practiced=created_recently,
            practice_history=[{"timestamp": created_recently, "quality": 2, "user_answer": "梯度很小", "note": "条件表述不完整"}],
            created_at=created_recently,
        ),
        ExerciseRecord(
            id="demoex04",
            question_text="牛顿法用于无约束优化时，搜索方向如何由梯度和 Hessian 矩阵确定？",
            answer="解线性方程 $H_k d_k=-g_k$，再令 $x_{k+1}=x_k+d_k$ 或配合线搜索。",
            explanation="当 Hessian 正定时，该方向是下降方向；非正定时通常需要修正。",
            source="Demo seed",
            subject=subject,
            chapter="无约束优化",
            tags=["牛顿法", "Hessian"],
            question_type="简答题",
            difficulty=3,
            linked_concepts=[{"name": "牛顿法", "confidence": 1.0, "source": "demo"}],
            status="new",
            created_at=created_recently,
        ),
        ExerciseRecord(
            id="demoex05",
            question_text="写出等式约束问题 $\min f(x)$，$h(x)=0$ 的 Lagrange 函数。",
            answer=r"$L(x,\lambda)=f(x)+\lambda^T h(x)$。",
            explanation="一阶条件由对 $x$ 与 $\lambda$ 的偏导数组成。",
            source="Demo seed",
            subject=subject,
            chapter="约束优化",
            tags=["Lagrange 函数", "等式约束"],
            question_type="公式题",
            difficulty=2,
            linked_concepts=[{"name": "Lagrange 函数", "confidence": 1.0, "source": "demo"}],
            status="new",
            created_at=created_recently,
        ),
        ExerciseRecord(
            id="demoex06",
            question_text="KKT 条件中的互补松弛条件表达了不等式约束与乘子之间的什么关系？",
            answer=r"对每个约束有 $\lambda_i g_i(x)=0$：约束不活跃时乘子为零，乘子非零时约束取等号。",
            explanation="互补松弛用于区分活跃约束与非活跃约束。",
            source="Demo seed",
            subject=subject,
            chapter="约束优化",
            tags=["KKT 条件", "互补松弛"],
            question_type="概念题",
            difficulty=3,
            linked_concepts=[{"name": "KKT 条件", "confidence": 1.0, "source": "demo"}],
            status="needs_review",
            created_at=created_recently,
        ),
    ]

    bank = get_exercise_bank(book_name, str(progress_dir))
    added_exercises = 0
    for record in exercises:
        if bank.get(record.id) is None:
            bank.add(record)
            added_exercises += 1

    mistake = MistakeRecord(
        id="demomis1",
        question_text="为什么驻点不一定是极小点？请给出一个一元函数反例。",
        user_answer="梯度为零就一定是极小点。",
        correct_answer="例如 $f(x)=x^3$ 在 $x=0$ 处导数为零，但该点不是极小点。",
        explanation="一阶必要条件只能筛出候选点，还需要二阶条件或函数局部性质进一步判断。",
        source="Demo seed",
        subject=subject,
        chapter="无约束优化",
        tags=["驻点", "二阶条件"],
        mistake_type=["概念不清"],
        difficulty=2,
        linked_concepts=[{"name": "驻点", "confidence": 1.0, "source": "demo"}],
        created_at=created_recently,
        sm2={
            "easiness": 2.5,
            "interval": 1,
            "repetitions": 0,
            "next_review": today,
            "last_review": None,
        },
    )
    mistake_book = get_mistake_book(book_name, str(progress_dir))
    existing_mistake = mistake_book.get(mistake.id)
    if existing_mistake is None:
        mistake_book.add_if_absent(mistake)

    conversation_id = "demo_docs_conversation"
    if not load_history(conversation_id):
        append_message(
            conversation_id,
            "user",
            "请结合教材说明 KKT 条件中互补松弛的含义。",
            book_name=book_name,
            subject=subject,
        )
        append_message(
            conversation_id,
            "assistant",
            r"互补松弛写作 $\lambda_i g_i(x)=0$。它表示第 $i$ 个不等式约束不活跃时，对应乘子为零；乘子非零时，该约束必须在边界上取等号。" + "\n\n*来源：约束优化*",
            book_name=book_name,
            subject=subject,
        )

    print(
        f"Seeded isolated demo: exercises_added={added_exercises}, "
        f"mistake_added={existing_mistake is None}, conversation_id={conversation_id}"
    )


if __name__ == "__main__":
    main()
