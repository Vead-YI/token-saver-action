"""
输出控制策略
通过注入简洁性要求和响应预算，减少模型输出 token。
"""

from __future__ import annotations

# 注入到 System Prompt 的简洁性指令（中文版）
CONCISE_SYSTEM_INJECTION_ZH = """
回答要求：
- 直接给出答案，不重复我的问题
- 代码用代码块，不用文字描述代码
- 省略显而易见的解释
- 如无必要，不加免责声明
""".strip()

# 英文版
CONCISE_SYSTEM_INJECTION_EN = """
Response rules:
- Answer directly, don't restate my question
- Use code blocks for code, not prose descriptions
- Skip obvious explanations
- Omit disclaimers unless critical
""".strip()


class OutputController:
    """构建可复用的输出约束指令。"""

    def __init__(self, language: str = "zh"):
        self.language = language

    def get_concise_injection(self) -> str:
        """返回基础简洁回答指令。"""
        return CONCISE_SYSTEM_INJECTION_ZH if self.language == "zh" else CONCISE_SYSTEM_INJECTION_EN

    def build_response_budget(
        self,
        max_sentences: int | None = None,
        prefer_bullets: bool = False,
        require_code_first: bool = False,
    ) -> str:
        """构建附加输出预算规则。"""
        lines = []
        if self.language == "zh":
            if max_sentences is not None:
                lines.append(f"- 非必要不超过 {max_sentences} 句")
            if prefer_bullets:
                lines.append("- 如需列点，保持扁平短列表")
            if require_code_first:
                lines.append("- 涉及修改建议时优先给代码或命令，再补充简述")
        else:
            if max_sentences is not None:
                lines.append(f"- Keep the answer within {max_sentences} sentences unless detail is necessary")
            if prefer_bullets:
                lines.append("- Use short flat bullet lists when listing multiple items")
            if require_code_first:
                lines.append("- For implementation help, show code or commands before explanation")

        if not lines:
            return ""

        title = "附加输出预算：" if self.language == "zh" else "Additional response budget:"
        return "\n".join([title, *lines])

    def apply_to_system(
        self,
        system_prompt: str = "",
        max_sentences: int | None = None,
        prefer_bullets: bool = False,
        require_code_first: bool = False,
    ) -> str:
        """把简洁指令和预算规则拼到 system prompt 末尾。"""
        sections = [system_prompt.strip()] if system_prompt.strip() else []
        sections.append(self.get_concise_injection())
        budget = self.build_response_budget(
            max_sentences=max_sentences,
            prefer_bullets=prefer_bullets,
            require_code_first=require_code_first,
        )
        if budget:
            sections.append(budget)
        return "\n\n".join(sections)
