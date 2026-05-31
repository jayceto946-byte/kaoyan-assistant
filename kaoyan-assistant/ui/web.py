"""Web界面 v3.0 — LangGraph 驱动"""
from pathlib import Path
from typing import Optional

import gradio as gr

from config import BOOKS_PATH, MULTIMODAL_ENABLED
from ingestion.pdf_parser import PDFParser
from ingestion.chapter_splitter import ChapterSplitter
from ingestion.vector_store import ChapterVectorStore
from ingestion.ocr import PDFImageExtractor, FormulaOCR
from graph.main_graph import run_graph
from agents.quiz import generate_quiz_from_state, check_answer
from memory.study_memory import StudyMemory
from memory.feedback import FeedbackLoop


class StudyWebUI:
    def __init__(self):
        self.vector_store = ChapterVectorStore()
        self.memory: Optional[StudyMemory] = None
        self.feedback: Optional[FeedbackLoop] = None
        self.current_book: Optional[str] = None

    def _ensure(self, name: str):
        if not self.memory or self.current_book != name:
            self.memory = StudyMemory(name)
            self.feedback = FeedbackLoop(name)
            self.current_book = name

    def import_book(self, path: str, progress=gr.Progress()):
        p = Path(path.strip())
        if not p.exists() or p.suffix != ".pdf":
            return "❌ 无效文件", []

        import shutil
        shutil.copy2(p, BOOKS_PATH / p.name)
        name = p.stem
        self._ensure(name)

        progress(0.1, "解析...")
        parser = PDFParser(BOOKS_PATH / p.name)
        chapters = parser.extract_chapters()
        parser.close()
        if not chapters:
            p2 = PDFParser(BOOKS_PATH / p.name)
            chapters = [{"title": name, "text": p2.extract_text()}]
            p2.close()

        progress(0.3, "分割...")
        splitter = ChapterSplitter()
        chunks = splitter.split_book(chapters)

        progress(0.5, "索引...")
        by_ch = {}
        for c in chunks:
            by_ch.setdefault(c["chapter"], []).append(c)
        for cn, cc in by_ch.items():
            self.vector_store.build_chapter_store(cn, cc)

        progress(0.8, "知识图谱...")
        from knowledge.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph(name)
        kg.build_from_chapters(chapters)

        progress(0.95)
        ext = PDFImageExtractor(BOOKS_PATH / p.name)
        ext.close()
        progress(1.0)
        return (
            f"✅ {name} | {len(chapters)}章 | {len(chunks)}块 | 图谱已构建",
            [{"title": ch["title"], "len": len(ch["text"])} for ch in chapters],
        )

    def ask(self, question: str, history: list, image=None):
        if not self._get_books():
            history.append((question, "⚠️ 请先导入教材"))
            return history
        if not self.current_book:
            self._ensure(self._get_books()[0].stem)

        images = [image] if image else []
        result = run_graph(question, book_name=self.current_book, user_images=images)

        answer = result.get("final_output", "")
        chs = result.get("target_chapters", [])
        intent = result.get("intent", "")
        answer += f"\n\n---\n🎯 {intent} | 📖 {','.join(chs[:3])}"

        history.append((question, answer))
        return history

    def show_progress(self):
        if not self.memory:
            return "⚠️ 请先导入", "", "", ""
        stats = self.memory.get_stats()
        weak = self.memory.get_weakness()

        st = (
            f"已学: {stats['chapters_studied']}章 | "
            f"做题: {stats['total_quiz']} | "
            f"正确率: {stats['accuracy']}% | "
            f"连续: {stats['streak']}天\n"
            f"SR知识点: {stats.get('sr_total',0)} | "
            f"已掌握: {stats.get('sr_mastered',0)} | "
            f"待复习: {stats.get('sr_due_today',0)}"
        )
        wk = "\n".join(f"- ⚠️ {w}" for w in weak[:10]) if weak else "无"

        due = self.memory.get_due_reviews()
        dr = "\n".join(f"- [{c['chapter']}] {c['knowledge_point'][:40]}" for c in due[:10]) if due else "🎉"

        weekly = self.memory.get_weekly_schedule()
        wl = "\n".join(f"- {d}: {c}个" for d, c in list(weekly.items())[:7])

        return st, wk, dr, wl

    def do_ocr(self, image, question: str):
        if not image:
            return "⚠️ 请上传图片"
        if not MULTIMODAL_ENABLED:
            return "⚠️ 需配置 Kimi K2.6"
        ocr = FormulaOCR()
        if question.strip():
            return ocr.multimodal_ask(question, [image])
        return ocr.extract_formulas(image)

    def do_kg(self, concept: str):
        if not self.current_book:
            return "⚠️ 请先导入"
        from knowledge.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph(self.current_book)
        concepts = list(kg.graph.keys())
        if not concepts:
            return "图谱为空"
        if concept:
            related = kg.find_related(concept)
            path = kg.find_path(concept)
            return (
                f"**概念**: {concept}\n\n"
                f"**关联**: {', '.join(related[:10]) if related else '无'}\n\n"
                f"**学习路径**: {' → '.join(path)}"
            )
        return "概念总数: " + str(len(concepts)) + "\n\n" + "\n".join(f"- {c}" for c in list(concepts)[:30])

    def _get_books(self):
        return list(BOOKS_PATH.glob("*.pdf"))

    def get_chapters(self):
        return self.vector_store.get_chapter_names()

    def launch(self, share=False, port=7860):
        with gr.Blocks(title="📚 考研辅助系统 v3.0", theme="soft") as app:
            gr.Markdown("# 📚 考研智能辅助系统 v3.0 (LangGraph)")
            gr.Markdown("Planner → Retrieve → Chapter → Generate → Feedback")

            with gr.Tabs():
                with gr.TabItem("📖 导入"):
                    pdf_i = gr.Textbox(label="PDF路径", placeholder="D:/books/高数.pdf", scale=3)
                    imp_btn = gr.Button("🚀 导入", variant="primary", scale=1)
                    imp_out = gr.Markdown()
                    ch_disp = gr.Dataframe(headers=["章节", "长度"])
                    imp_btn.click(self.import_book, [pdf_i], [imp_out, ch_disp])

                with gr.TabItem("💬 问答"):
                    chatbot = gr.Chatbot(height=350)
                    with gr.Row():
                        qi = gr.Textbox(label="问题", placeholder="任意问题...", scale=3)
                        imgi = gr.Image(label="📷 图片(可选)", type="filepath", scale=1)
                    with gr.Row():
                        ask_b = gr.Button("🤔 提问", variant="primary")
                        clr_b = gr.Button("🗑️ 清空")
                    ask_b.click(self.ask, [qi, chatbot, imgi], [chatbot])
                    qi.submit(self.ask, [qi, chatbot, imgi], [chatbot])
                    clr_b.click(lambda: [], None, chatbot)

                with gr.TabItem("📝 练习"):
                    ch_dd = gr.Dropdown(label="章节", choices=[])
                    gr.Button("🔄 刷新").click(lambda: gr.Dropdown(choices=self.get_chapters()), outputs=[ch_dd])
                    quiz_b = gr.Button("📄 生成题目")
                    quiz_html = gr.Markdown()
                    quiz_st = gr.State([])
                    quiz_b.click(
                        lambda ch: ("", generate_quiz_from_state({"target_chapters": [ch]})),
                        [ch_dd], [quiz_html, quiz_st]
                    )
                    quiz_a = gr.Textbox(label="答案")
                    quiz_f = gr.Markdown()
                    gr.Button("✅ 检查").click(
                        lambda qs, a: check_answer(qs[0], a) if qs else {"feedback": "先生成题目"},
                        [quiz_st, quiz_a], [quiz_f]
                    )

                with gr.TabItem("📊 进度"):
                    gr.Button("🔄 刷新").click(self.show_progress, outputs=[
                        gr.Markdown(), gr.Markdown(), gr.Markdown(), gr.Markdown()
                    ])

                with gr.TabItem("🔗 知识图谱"):
                    kg_i = gr.Textbox(label="概念名 (留空=全览)")
                    kg_b = gr.Button("🔍 查询")
                    kg_o = gr.Markdown()
                    kg_b.click(self.do_kg, [kg_i], [kg_o])

                with gr.TabItem("📷 OCR"):
                    o_i = gr.Image(label="图片", type="filepath")
                    o_q = gr.Textbox(label="问题(可选)")
                    o_b = gr.Button("🔍 识别")
                    o_o = gr.Markdown()
                    o_b.click(self.do_ocr, [o_i, o_q], [o_o])

            gr.Markdown("---\nLangGraph v3.0 | 需配置 MOONSHOT_API_KEY")

        books = self._get_books()
        if books:
            self._ensure(books[0].stem)

        app.launch(share=share, server_port=port)
