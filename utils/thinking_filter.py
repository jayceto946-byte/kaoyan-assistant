"""DeepSeek thinking 内容过滤工具

DeepSeek V4 Pro 在 thinking 模式下会输出 <think>...</think> 包裹的推理链，
需要过滤后才能展示给用户。
"""


class ThinkingFilter:
    """流式 thinking 过滤器，支持跨 chunk 的 <think>...</think> 标签。"""

    def __init__(self):
        self.in_thinking = False
        self.buffer = ""
        self._open_tag = "<think>"
        self._close_tag = "</think>"

    @staticmethod
    def _partial_tag_length(text: str, tag: str) -> int:
        """Return the longest suffix of text that can start a tag."""
        lowered = text.lower()
        for length in range(min(len(lowered), len(tag) - 1), 0, -1):
            if lowered.endswith(tag[:length]):
                return length
        return 0

    def filter(self, text: str) -> str:
        """过滤文本中的 thinking 内容，返回干净的文本。"""
        if not text:
            return ""

        self.buffer += text
        result = []

        while self.buffer:
            lowered = self.buffer.lower()
            if self.in_thinking:
                end = lowered.find(self._close_tag)
                if end == -1:
                    # Discard confirmed thinking content, but retain a possible
                    # split closing tag for the next chunk.
                    keep = self._partial_tag_length(self.buffer, self._close_tag)
                    self.buffer = self.buffer[-keep:] if keep else ""
                    break
                self.buffer = self.buffer[end + len(self._close_tag):]
                self.in_thinking = False
            else:
                start = lowered.find(self._open_tag)
                if start == -1:
                    # Emit confirmed normal text, but retain a possible split
                    # opening tag so it can never leak as ordinary output.
                    keep = self._partial_tag_length(self.buffer, self._open_tag)
                    if keep:
                        result.append(self.buffer[:-keep])
                        self.buffer = self.buffer[-keep:]
                    else:
                        result.append(self.buffer)
                        self.buffer = ""
                    break
                result.append(self.buffer[:start])
                self.buffer = self.buffer[start + len(self._open_tag):]
                self.in_thinking = True

        return "".join(result)

    def flush(self) -> str:
        """流结束时调用，输出 buffer 中剩余的非 thinking 内容。"""
        if self.in_thinking:
            self.buffer = ""
            self.in_thinking = False
            return ""
        if not self.buffer:
            return ""
        # A retained suffix is an incomplete opening tag. Discard it rather
        # than exposing a fragment of a reasoning marker.
        if self._open_tag.startswith(self.buffer.lower()):
            self.buffer = ""
            return ""
        text = self.buffer
        self.buffer = ""
        return text


def strip_thinking(text: str) -> str:
    """一次性安全过滤完整或未闭合的 thinking 内容。"""
    if not text:
        return text
    stream_filter = ThinkingFilter()
    return (stream_filter.filter(text) + stream_filter.flush()).strip()
