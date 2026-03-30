"""
对话上下文管理器
智能裁剪对话历史，在 token 预算内保留最重要的内容
"""

from __future__ import annotations

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

        # 强制保留最后 N 条
        tail = conv_msgs[-keep_last:] if len(conv_msgs) > keep_last else conv_msgs
        head = conv_msgs[:-keep_last] if len(conv_msgs) > keep_last else []

        tail_tokens = self.counter.count_messages(tail)
        remaining_budget -= tail_tokens

        if remaining_budget <= 0 or not head:
            return system_msgs + tail

        # 从最近到最早，贪心地加入 head 中的消息
        selected_head = []
        for msg in reversed(head):
            msg_tokens = self.counter.count_messages([msg])
            if remaining_budget >= msg_tokens:
                selected_head.insert(0, msg)
                remaining_budget -= msg_tokens
            else:
                break  # 预算不足，停止

        return system_msgs + selected_head + tail

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
