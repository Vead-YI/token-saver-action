"""
Token 计数器
支持 tiktoken（OpenAI 系列模型）和字符估算（其他模型）
"""

from __future__ import annotations

try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
except ImportError:
    _TIKTOKEN_AVAILABLE = False


# 各模型每 token 平均字符数（用于无 tiktoken 时的估算）
_CHAR_PER_TOKEN = {
    "default": 3.5,
    "chinese": 1.5,  # 中文每个字约 1.5 token（GPT-4 tokenizer）
}

# tiktoken 编码器映射
_TIKTOKEN_ENCODINGS = {
    "gpt-4o": "o200k_base",
    "gpt-4": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
    "claude": "cl100k_base",  # 近似
    "default": "cl100k_base",
}


class TokenCounter:
    """
    Token 计数工具

    优先使用 tiktoken 精确计数，不可用时退回字符估算。
    """

    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        self._encoder = None

        if _TIKTOKEN_AVAILABLE:
            encoding_name = _TIKTOKEN_ENCODINGS.get(model, _TIKTOKEN_ENCODINGS["default"])
            try:
                self._encoder = tiktoken.get_encoding(encoding_name)
            except Exception:
                self._encoder = None

    def count(self, text: str) -> int:
        """精确或估算 Token 数量"""
        if not text:
            return 0

        if self._encoder is not None:
            return len(self._encoder.encode(text))

        # 退回估算：中文字符按 1.5 token，其他按 0.25 token（4 chars = 1 token）
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars / 4)

    def count_messages(self, messages: list[dict]) -> int:
        """统计 OpenAI 格式消息列表的总 Token 数"""
        total = 0
        for msg in messages:
            # 每条消息有约 4 token 的格式开销
            total += 4
            total += self.count(msg.get("content", ""))
            total += self.count(msg.get("role", ""))
        total += 2  # 对话结束标记
        return total

    def estimate_cost(self, tokens: int, model: str | None = None) -> dict:
        """估算 API 调用费用（美元）"""
        model = model or self.model
        # 2024 年价格参考（每 1M tokens）
        prices = {
            "gpt-4o": {"input": 5.0, "output": 15.0},
            "gpt-4": {"input": 30.0, "output": 60.0},
            "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
            "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
            "claude-3-haiku": {"input": 0.25, "output": 1.25},
        }
        price = prices.get(model, prices["gpt-4o"])
        return {
            "input_cost_usd": tokens * price["input"] / 1_000_000,
            "output_cost_usd": tokens * price["output"] / 1_000_000,
        }
