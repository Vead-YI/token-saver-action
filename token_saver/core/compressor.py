"""
文本压缩器
通过规则和启发式方法去除 Prompt 中的冗余内容
"""

from __future__ import annotations

import re


# 中文礼貌用语模式（可安全删除）
_POLITE_PATTERNS_ZH = [
    r"(麻烦|劳烦|烦请|辛苦|拜托)[你您了]?[，,]?\s*",
    r"谢谢[你您]?[的]?(帮助|回答|解答|支持)?[！!。.]?\s*",
    r"感谢[你您]?[的]?(帮助|回答|解答|支持)?[！!。.]?\s*",
    r"非常感[激谢][！!。.]?\s*",
    r"[十分非常很]感[激谢][！!。.]?\s*",
    r"[希望]?期待[你您的]?(回复|回答)[！!。.]?\s*",
]

# 英文礼貌用语模式
_POLITE_PATTERNS_EN = [
    r"\bplease\b\s*",
    r"\bthank(?:s| you)\b[.!,]?\s*(?:very much|so much)?[.!]?\s*",
    r"\bi would appreciate\b[^.]*\.",
    r"\bif you could\b",
    r"\bwould you mind\b",
]

# 冗余引导语（"帮我..."、"你能..."）
_FILLER_PATTERNS = [
    r"^(你能|你可以|能不能|可以|帮我|帮忙|请帮我|请帮忙)[吗嘛]?[，,]?\s*",
    r"^(我想|我需要|我希望|我要)[你您]?(帮我|帮忙|来)?\s*",
    r"^(Can you|Could you|Would you|Please)\s+",
    r"^(I need you to|I want you to|I'd like you to)\s+",
]

# 重复的结尾语
_TRAILING_PATTERNS = [
    r"[，,。.]\s*(谢谢|感谢|拜托|麻烦)[你您]?[了的]?[！!。.]?\s*$",
    r"\s*(Thanks|Thank you)[.!]?\s*$",
]


class TextCompressor:
    """
    基于规则的文本压缩器

    三个压缩级别：
    - light: 只去除明显冗余（礼貌用语、重复空行）
    - moderate: 去除冗余 + 合并重复意图 + 结构化
    - aggressive: 最大压缩，可能轻微改变表达方式
    """

    def compress(self, text: str, level: str = "moderate") -> str:
        """
        压缩文本

        Args:
            text: 原始文本
            level: "light" | "moderate" | "aggressive"

        Returns:
            压缩后的文本
        """
        if not text or not text.strip():
            return text

        result = text

        # Level 1: light — 基础清理
        result = self._remove_polite_phrases(result)
        result = self._clean_whitespace(result)

        if level in ("moderate", "aggressive"):
            result = self._remove_filler_openers(result)
            result = self._remove_trailing_pleasantries(result)
            result = self._deduplicate_sentences(result)

        if level == "aggressive":
            result = self._compress_code_context(result)
            result = self._shorten_instructions(result)

        return result.strip()

    def _remove_polite_phrases(self, text: str) -> str:
        """去除礼貌用语"""
        for pattern in _POLITE_PATTERNS_ZH + _POLITE_PATTERNS_EN:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        return text

    def _remove_filler_openers(self, text: str) -> str:
        """去除冗余引导语"""
        for pattern in _FILLER_PATTERNS:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)
        return text

    def _remove_trailing_pleasantries(self, text: str) -> str:
        """去除结尾礼貌语"""
        for pattern in _TRAILING_PATTERNS:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        return text

    def _clean_whitespace(self, text: str) -> str:
        """清理多余空白和残留标点"""
        # 多个空行合并为一个
        text = re.sub(r"\n{3,}", "\n\n", text)
        # 行尾空格
        text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
        # 多个空格合并
        text = re.sub(r"  +", " ", text)
        # 清理连续的中文标点（如 "，，" "。。"）
        text = re.sub(r"[，,]{2,}", "，", text)
        text = re.sub(r"[。.]{2,}", "。", text)
        # 清理句首/句尾多余的标点
        text = re.sub(r"^[，,。、；;]+", "", text, flags=re.MULTILINE)
        text = re.sub(r"[，,、；;]+$", "", text, flags=re.MULTILINE)
        # 清理 "very much!" 这类英文残留（thank you 被删后留下的）
        text = re.sub(r"(?i)^(very much|so much)[.!]?\s*$", "", text, flags=re.MULTILINE)
        return text

    def _deduplicate_sentences(self, text: str) -> str:
        """去除重复的句子/段落"""
        lines = text.split("\n")
        seen = set()
        result = []
        for line in lines:
            normalized = line.strip().lower()
            if normalized and normalized in seen:
                continue
            if normalized:
                seen.add(normalized)
            result.append(line)
        return "\n".join(result)

    def _compress_code_context(self, text: str) -> str:
        """
        压缩代码上下文：
        - 移除代码中的注释（如果代码本身已经很清晰）
        - 压缩连续的空行
        """
        # 移除 Python 单行注释（保留文档字符串）
        text = re.sub(r"(?m)^(\s*)#(?!!).*$", r"\1", text)
        # 移除 JS/TS 单行注释
        text = re.sub(r"(?m)^\s*//.*$", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text

    def _shorten_instructions(self, text: str) -> str:
        """
        将常见的冗长指令模式替换为简洁版本
        """
        replacements = [
            # 中文
            (r"请[你您]?详细[地的]?解释[一下]?", "解释"),
            (r"请[你您]?帮[我]?分析[一下]?", "分析"),
            (r"请[你您]?告诉[我]?", "说明"),
            (r"如果[有]?[任何]?问题[的话]?[，,]?请[帮我]?修复", "修复问题"),
            (r"有没有[什么]?可以优化的[地方]?", "优化建议"),
            # 英文
            (r"(?i)please provide a detailed explanation of", "explain"),
            (r"(?i)can you please help me (understand|analyze|fix)", r"\1"),
            (r"(?i)i would like you to", ""),
        ]
        for pattern, replacement in replacements:
            text = re.sub(pattern, replacement, text)
        return text
