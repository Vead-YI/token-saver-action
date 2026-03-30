"""
token_saver — 节省Token行动
帮助用户在使用 AI、AI Agent 和 OpenClaw 时节约 Token 消耗
"""

from .core.compressor import TextCompressor
from .core.context_manager import ContextManager
from .core.token_counter import TokenCounter

__version__ = "0.1.0"
__all__ = ["TokenSaver", "TextCompressor", "ContextManager", "TokenCounter"]


class TokenSaver:
    """主入口类，整合所有节省策略"""

    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        self.counter = TokenCounter(model=model)
        self.compressor = TextCompressor()
        self.context_manager = ContextManager(counter=self.counter)

    def count_tokens(self, text: str) -> int:
        """统计文本的 Token 数量"""
        return self.counter.count(text)

    def compress_prompt(self, prompt: str, level: str = "moderate") -> str:
        """
        压缩 Prompt，去除冗余内容

        Args:
            prompt: 原始 Prompt
            level: 压缩级别 "light" | "moderate" | "aggressive"

        Returns:
            压缩后的 Prompt
        """
        return self.compressor.compress(prompt, level=level)

    def optimize_history(self, messages: list, max_tokens: int = 4000) -> list:
        """
        优化对话历史，在 token 预算内保留最重要的轮次

        Args:
            messages: OpenAI 格式的消息列表 [{"role": ..., "content": ...}]
            max_tokens: 最大 token 预算

        Returns:
            优化后的消息列表
        """
        return self.context_manager.prune(messages, max_tokens=max_tokens)

    def stats(self, text: str) -> dict:
        """返回文本的 Token 统计信息"""
        count = self.counter.count(text)
        return {
            "tokens": count,
            "chars": len(text),
            "ratio": len(text) / max(count, 1),
            "estimated_cost_gpt4o": count * 0.000005,  # $5/1M input tokens
        }
