"""DeepSeek thinking 内容过滤工具

DeepSeek V4 Pro 在 thinking 模式下会输出 <think>...</think> 包裹的推理链，
需要过滤后才能展示给用户。
"""
import re


class ThinkingFilter:
    """流式 thinking 过滤器，支持跨 chunk 的 <think>...</think> 标签。

    Usage:
        tf = ThinkingFilter()
        for chunk in llm.stream(prompt):
            clean = tf.filter(chunk.content)
            if clean:
                yield clean
        # 流结束时 flush 剩余内容
        final = tf.flush()
        if final:
            yield final
    """

    def __init__(self):
        self.in_thinking = False
        self.buffer = ""

    def filter(self, text: str) -> str:
        """过滤文本中的 thinking 内容，返回干净的文本。"""
        if not text:
            return ""

        self.buffer += text
        result = []

        while self.buffer:
            if self.in_thinking:
                end = self.buffer.find("</think>")
                if end == -1:
                    # 整个 buffer 都在 thinking 中，等待更多数据
                    self.buffer = ""
                    break
                # 找到结束标签，保留之后的内容继续处理
                self.buffer = self.buffer[end + len("</think>"):]
                self.in_thinking = False
            else:
                start = self.buffer.find("<think>")
                if start == -1:
                    # 没有 thinking 标签，全部输出
                    result.append(self.buffer)
                    self.buffer = ""
                    break
                # 输出 think 之前的内容
                result.append(self.buffer[:start])
                self.buffer = self.buffer[start + len("<think>"):]
                self.in_thinking = True

        return "".join(result)

    def flush(self) -> str:
        """流结束时调用，输出 buffer 中剩余的非 thinking 内容。"""
        if not self.buffer:
            return ""
        if self.in_thinking:
            # 流结束还没看到 </think>，丢弃剩余内容
            self.buffer = ""
            self.in_thinking = False
            return ""
        text = self.buffer
        self.buffer = ""
        return text


def strip_thinking(text: str) -> str:
    """一次性过滤文本中的所有 <think>...</think> 内容。

    Usage:
        clean = strip_thinking(llm.invoke(prompt).content)
    """
    if not text:
        return text
    # 非贪婪匹配，支持多行
    pattern = re.compile(r"<think>.*?</think>", re.DOTALL)
    return pattern.sub("", text).strip()
