"""
Prompt 优化器
提供高层 Prompt 优化策略，包括结构化、去冗余、注入简洁性指令
"""

from __future__ import annotations

from ..core.compressor import TextCompressor
from ..core.token_counter import TokenCounter
from .output_controller import (
    CONCISE_SYSTEM_INJECTION_EN,
    CONCISE_SYSTEM_INJECTION_ZH,
    OutputController,
)


class PromptOptimizer:
    """
    Prompt 优化器

    功能：
    1. 压缩用户 Prompt（去冗余）
    2. 注入简洁性指令到 System Prompt
    3. 将长段落转换为结构化列表
    4. 分析 Prompt 并给出优化建议
    """

    def __init__(self, model: str = "gpt-4o", language: str = "zh"):
        self.compressor = TextCompressor()
        self.counter = TokenCounter(model=model)
        self.language = language
        self.output_controller = OutputController(language=language)

    def optimize(
        self,
        messages: list[dict],
        inject_concise: bool = True,
        compress_user: bool = True,
        compress_level: str = "moderate",
    ) -> list[dict]:
        """
        优化完整的消息列表

        Args:
            messages: OpenAI 格式消息列表
            inject_concise: 是否注入简洁性指令
            compress_user: 是否压缩用户消息
            compress_level: 压缩级别

        Returns:
            优化后的消息列表
        """
        result = []
        system_injected = False

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "system":
                if inject_concise and not system_injected:
                    content = self._inject_concise_instruction(content)
                    system_injected = True
                result.append({**msg, "content": content})

            elif role == "user":
                if compress_user:
                    content = self.compressor.compress(content, level=compress_level)
                result.append({**msg, "content": content})

            else:
                result.append(msg)

        # 如果没有 system 消息但需要注入简洁指令
        if inject_concise and not system_injected:
            injection = self._get_concise_injection()
            result.insert(0, {"role": "system", "content": injection})

        return result

    def analyze(self, prompt: str) -> dict:
        """
        分析 Prompt 并给出优化建议

        Returns:
            {
                "original_tokens": int,
                "suggestions": [{"type": str, "description": str, "savings_estimate": str}],
                "optimized_preview": str,
            }
        """
        original_tokens = self.counter.count(prompt)
        suggestions = []

        # 检测礼貌用语
        import re
        polite_patterns = ["请", "谢谢", "感谢", "麻烦", "please", "thank you", "thanks"]
        found_polite = [p for p in polite_patterns if p.lower() in prompt.lower()]
        if found_polite:
            suggestions.append({
                "type": "polite_phrases",
                "description": f"发现礼貌用语: {', '.join(found_polite)}，可安全删除",
                "savings_estimate": "5-15%",
            })

        # 检测重复意图
        sentences = re.split(r"[。.!！?？\n]", prompt)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
        if len(sentences) > 3:
            suggestions.append({
                "type": "redundant_intent",
                "description": f"Prompt 包含 {len(sentences)} 个句子，可能有重复意图",
                "savings_estimate": "10-30%",
            })

        # 检测过长的背景描述
        if original_tokens > 200:
            suggestions.append({
                "type": "long_context",
                "description": "Prompt 较长，考虑只保留 AI 需要的关键信息",
                "savings_estimate": "20-40%",
            })

        # 生成优化预览
        optimized = self.compressor.compress(prompt, level="moderate")
        optimized_tokens = self.counter.count(optimized)

        return {
            "original_tokens": original_tokens,
            "optimized_tokens": optimized_tokens,
            "savings": original_tokens - optimized_tokens,
            "savings_pct": round((1 - optimized_tokens / max(original_tokens, 1)) * 100, 1),
            "suggestions": suggestions,
            "optimized_preview": optimized,
        }

    def _inject_concise_instruction(self, system_content: str) -> str:
        """将简洁性指令注入到 System Prompt"""
        injection = self._get_concise_injection()
        if injection in system_content:
            return system_content  # 已经注入过了
        return system_content + "\n\n" + injection

    def _get_concise_injection(self) -> str:
        return self.output_controller.get_concise_injection()

    def structurize(self, text: str) -> str:
        """
        将长段落描述转换为结构化列表
        （简单启发式：按句号/逗号分割，转为列表）
        """
        import re
        # 检测是否已经是列表格式
        if re.search(r"^\s*[-*•\d]", text, re.MULTILINE):
            return text  # 已经是列表了

        # 按句子分割
        sentences = re.split(r"[。；;]", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 3]

        if len(sentences) <= 2:
            return text  # 太短，不需要结构化

        return "\n".join(f"- {s}" for s in sentences)
