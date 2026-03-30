"""
历史裁剪策略
对 ContextManager 做一层更贴近策略层的封装，方便直接暴露给用户和集成层。
"""

from __future__ import annotations

from ..core.context_manager import ContextManager
from ..core.token_counter import TokenCounter


class HistoryPruner:
    """高层历史裁剪器，补齐 README 中承诺的策略模块。"""

    def __init__(self, model: str = "gpt-4o", counter: TokenCounter | None = None):
        self.counter = counter or TokenCounter(model=model)
        self.manager = ContextManager(counter=self.counter)

    def prune(
        self,
        messages: list[dict],
        max_tokens: int = 4000,
        keep_last: int = 4,
        keep_system: bool = True,
    ) -> list[dict]:
        """裁剪到预算内，同时尽量保留最近和高价值消息。"""
        return self.manager.prune(
            messages,
            max_tokens=max_tokens,
            keep_last=keep_last,
            keep_system=keep_system,
        )

    def summarize_then_prune(
        self,
        messages: list[dict],
        max_tokens: int = 4000,
        keep_last: int = 6,
    ) -> list[dict]:
        """先用摘要占位符压缩早期消息，再做预算裁剪。"""
        summarized = self.manager.summarize_old_messages(messages, keep_last=keep_last)
        return self.manager.prune(
            summarized,
            max_tokens=max_tokens,
            keep_last=min(keep_last + 1, len(summarized)),
        )

    def analyze(self, messages: list[dict], max_tokens: int = 4000, keep_last: int = 4) -> dict:
        """输出裁剪前后的对比数据，便于 CLI/MCP 展示。"""
        pruned = self.prune(messages, max_tokens=max_tokens, keep_last=keep_last)
        original_tokens = self.counter.count_messages(messages)
        pruned_tokens = self.counter.count_messages(pruned)
        return {
            "original_messages": len(messages),
            "pruned_messages": len(pruned),
            "original_tokens": original_tokens,
            "pruned_tokens": pruned_tokens,
            "savings_tokens": original_tokens - pruned_tokens,
            "savings_pct": round((1 - pruned_tokens / max(original_tokens, 1)) * 100, 1),
            "messages": pruned,
        }
