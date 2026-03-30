"""
对话上下文管理器
智能裁剪对话历史，在 token 预算内保留最重要的内容
"""

from __future__ import annotations

import re

from .token_counter import TokenCounter


class ContextManager:
    """
    对话上下文管理器

    策略：
    1. 始终保留 system prompt
    2. 始终保留最近 N 轮对话
    3. 对早期对话按重要性评分，优先保留
    4. 超出预算时，对早期对话做摘要压缩
    """

    def __init__(self, counter: TokenCounter | None = None, model: str = "gpt-4o"):
        self.counter = counter or TokenCounter(model=model)

    def prune(
        self,
        messages: list[dict],
        max_tokens: int = 4000,
        keep_last: int = 4,
        keep_system: bool = True,
    ) -> list[dict]:
        """
        裁剪对话历史到 token 预算内

        Args:
            messages: OpenAI 格式消息列表
            max_tokens: 最大 token 预算
            keep_last: 强制保留最后 N 条消息
            keep_system: 是否保留 system prompt

        Returns:
            裁剪后的消息列表
        """
        if not messages:
            return messages

        # 分离 system 消息和对话消息
        system_msgs = [m for m in messages if m.get("role") == "system"] if keep_system else []
        conv_msgs = [m for m in messages if m.get("role") != "system"]

        # 计算 system 消息占用的 token
        system_tokens = self.counter.count_messages(system_msgs)
        remaining_budget = max_tokens - system_tokens

        if remaining_budget <= 0:
            return system_msgs

        # 优先保留最后 N 条，但如果预算不足，也要尽量保留最近且重要的消息
        tail_start = max(len(conv_msgs) - keep_last, 0)
        tail_candidates = list(enumerate(conv_msgs[tail_start:], start=tail_start))
        head_candidates = list(enumerate(conv_msgs[:tail_start]))

        tail_messages = [msg for _, msg in tail_candidates]
        tail_tokens = self.counter.count_messages(tail_messages) if tail_messages else 0
        if tail_messages and tail_tokens <= remaining_budget:
            selected_tail = tail_messages
            remaining_budget -= tail_tokens
        else:
            selected_tail, remaining_budget = self._select_recent_messages(
                tail_candidates, remaining_budget
            )

        if not head_candidates or remaining_budget <= 0:
            return system_msgs + selected_tail

        selected_head = self._select_priority_messages(head_candidates, remaining_budget)
        return system_msgs + selected_head + selected_tail

    def summarize_old_messages(self, messages: list[dict], keep_last: int = 6) -> list[dict]:
        """
        将早期消息替换为摘要（需要 AI 调用，此处返回占位符）

        实际使用时，应将 summary_prompt 发给 AI 获取摘要，
        然后用摘要替换早期消息。
        """
        if len(messages) <= keep_last:
            return messages

        old = messages[:-keep_last]
        recent = messages[-keep_last:]

        # 生成摘要 prompt（调用方负责实际执行）
        summary_prompt = self._build_summary_prompt(old)

        # 返回摘要占位符 + 最近消息
        summary_msg = {
            "role": "system",
            "content": f"[早期对话摘要 - 请调用 AI 替换此内容]\n{summary_prompt}",
            "_is_summary": True,
            "_original_count": len(old),
        }
        return [summary_msg] + recent

    def _build_summary_prompt(self, messages: list[dict]) -> str:
        """构建摘要请求 prompt"""
        lines = ["以下是早期对话记录，请用 2-3 句话总结关键信息：\n"]
        for msg in messages:
            role = "用户" if msg.get("role") == "user" else "AI"
            content = msg.get("content", "")[:200]  # 截断过长内容
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def get_stats(self, messages: list[dict]) -> dict:
        """获取对话历史的统计信息"""
        total_tokens = self.counter.count_messages(messages)
        by_role = {}
        for msg in messages:
            role = msg.get("role", "unknown")
            tokens = self.counter.count(msg.get("content", ""))
            by_role[role] = by_role.get(role, 0) + tokens

        return {
            "total_messages": len(messages),
            "total_tokens": total_tokens,
            "tokens_by_role": by_role,
            "avg_tokens_per_message": total_tokens // max(len(messages), 1),
        }

    def _select_recent_messages(
        self,
        indexed_messages: list[tuple[int, dict]],
        remaining_budget: int,
    ) -> tuple[list[dict], int]:
        """尽可能保留最近消息，预算不足时按时间倒序回退。"""
        selected: list[tuple[int, dict]] = []

        for idx, msg in reversed(indexed_messages):
            msg_tokens = self._message_tokens(msg)
            if remaining_budget < msg_tokens:
                continue
            selected.append((idx, msg))
            remaining_budget -= msg_tokens

        selected.sort(key=lambda item: item[0])
        return [msg for _, msg in selected], remaining_budget

    def _select_priority_messages(
        self,
        indexed_messages: list[tuple[int, dict]],
        remaining_budget: int,
    ) -> list[dict]:
        """在剩余预算内保留更重要的早期消息。"""
        scored = []
        for idx, msg in indexed_messages:
            score = self._message_priority(msg, idx, len(indexed_messages))
            tokens = self._message_tokens(msg)
            scored.append((score, idx, tokens, msg))

        scored.sort(key=lambda item: (-item[0], -item[1]))

        selected: list[tuple[int, dict]] = []
        for _, idx, tokens, msg in scored:
            if tokens > remaining_budget:
                continue
            selected.append((idx, msg))
            remaining_budget -= tokens

        selected.sort(key=lambda item: item[0])
        return [msg for _, msg in selected]

    def _message_priority(self, msg: dict, idx: int, total: int) -> int:
        """根据角色、内容特征和时间位置粗略评估消息价值。"""
        role = msg.get("role", "")
        content = str(msg.get("content", ""))

        base_scores = {
            "user": 40,
            "assistant": 24,
            "tool": 28,
        }
        score = base_scores.get(role, 18)

        lowered = content.lower()
        important_patterns = [
            r"```",
            r"\b(error|exception|traceback|failing|failed|bug|fix)\b",
            r"\b(todo|requirement|constraint|expected|actual)\b",
            r"[？?]",
        ]
        for pattern in important_patterns:
            if re.search(pattern, lowered, flags=re.IGNORECASE):
                score += 8

        if len(content) > 400:
            score += 4

        # 越近的早期消息优先级越高，但不完全压倒内容价值
        if total > 0:
            score += int((idx / total) * 10)

        return score

    def _message_tokens(self, msg: dict) -> int:
        """估算单条消息的 token 成本，避免重复计算对话收尾开销。"""
        return 4 + self.counter.count(msg.get("role", "")) + self.counter.count(msg.get("content", ""))
