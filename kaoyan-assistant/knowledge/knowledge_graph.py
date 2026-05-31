"""知识图谱 — 概念间依赖和关联关系"""
import json
from pathlib import Path
from config import PROGRESS_PATH


class KnowledgeGraph:
    """考研知识点图谱

    存储：概念A → 前置依赖 → 概念B → 后续延伸 → 概念C
    支持：查找相关概念、查找学习路径
    """

    def __init__(self, book_name: str):
        self.book_name = book_name
        self.file = Path(PROGRESS_PATH) / book_name / "knowledge_graph.json"
        self.file.parent.mkdir(parents=True, exist_ok=True)

        # 邻接表: {concept: {prerequisites: [], extensions: [], chapter: ""}}
        self.graph = self._load()

    def _load(self) -> dict:
        if self.file.exists():
            with open(self.file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save(self):
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(self.graph, f, ensure_ascii=False, indent=2)

    def add_concept(self, name: str, chapter: str,
                    prerequisites: list[str] = None,
                    extensions: list[str] = None):
        """添加概念节点"""
        if name not in self.graph:
            self.graph[name] = {"chapter": chapter}
        self.graph[name].setdefault("prerequisites", [])
        self.graph[name].setdefault("extensions", [])

        if prerequisites:
            for p in prerequisites:
                if p not in self.graph[name]["prerequisites"]:
                    self.graph[name]["prerequisites"].append(p)
                # 反向关联
                if p not in self.graph:
                    self.graph[p] = {"chapter": chapter}
                self.graph[p].setdefault("extensions", [])
                if name not in self.graph[p]["extensions"]:
                    self.graph[p]["extensions"].append(name)

        if extensions:
            for e in extensions:
                if e not in self.graph[name]["extensions"]:
                    self.graph[name]["extensions"].append(e)

        self._save()

    def get_prerequisites(self, concept: str) -> list[str]:
        return self.graph.get(concept, {}).get("prerequisites", [])

    def get_extensions(self, concept: str) -> list[str]:
        return self.graph.get(concept, {}).get("extensions", [])

    def find_path(self, concept: str, context: str = "") -> list[str]:
        """查找概念的学习路径（从基础到该概念）"""
        path = []
        visited = set()
        self._dfs_upstream(concept, path, visited)
        path.reverse()
        if concept not in path:
            path.append(concept)
        return path

    def _dfs_upstream(self, concept: str, path: list, visited: set):
        if concept in visited:
            return
        visited.add(concept)
        for prereq in self.get_prerequisites(concept):
            self._dfs_upstream(prereq, path, visited)
            if prereq not in path:
                path.append(prereq)

    def find_related(self, concept: str) -> list[str]:
        """查找所有关联概念"""
        related = set()
        related.update(self.get_prerequisites(concept))
        related.update(self.get_extensions(concept))
        # 同章节的其他概念
        ch = self.graph.get(concept, {}).get("chapter", "")
        if ch:
            for c, info in self.graph.items():
                if info.get("chapter") == ch and c != concept:
                    related.add(c)
        return list(related)

    def build_from_chapters(self, chapters_data: list[dict], llm=None):
        """从章节数据自动构建知识图谱（需LLM提取概念关系）"""
        if llm is None:
            from config import get_llm
            llm = get_llm(temperature=0)

        for ch in chapters_data:
            title = ch.get("title", "")
            text = ch.get("text", "")[:4000]
            if not text:
                continue

            prompt = f"""分析以下教材章节，提取核心概念及其依赖关系。

## 章节：{title}
## 内容
{text}

输出 JSON（不要其他）：
{{
  "concepts": [
    {{"name": "概念名", "prerequisites": ["前置概念1"], "extensions": ["后续概念1"]}}
  ]
}}
"""
            resp = llm.invoke(prompt).content.strip()
            if resp.startswith("```"):
                resp = resp.split("\n", 1)[-1].rsplit("\n", 1)[0]
            try:
                data = json.loads(resp)
                for c in data.get("concepts", []):
                    self.add_concept(
                        c["name"], title,
                        c.get("prerequisites", []),
                        c.get("extensions", []),
                    )
            except json.JSONDecodeError:
                continue
