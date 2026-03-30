"""
基础测试
"""

import pytest
from token_saver.core.token_counter import TokenCounter
from token_saver.core.compressor import TextCompressor
from token_saver.core.context_manager import ContextManager
from token_saver.strategies.file_reader import SmartFileReader
from token_saver.strategies.prompt_optimizer import PromptOptimizer


class TestTokenCounter:
    def setup_method(self):
        self.counter = TokenCounter(model="gpt-4o")

    def test_count_empty(self):
        assert self.counter.count("") == 0

    def test_count_english(self):
        # "Hello world" 约 2 tokens
        count = self.counter.count("Hello world")
        assert 1 <= count <= 5

    def test_count_chinese(self):
        # 中文字符 token 数应 >= 字符数
        text = "你好世界"
        count = self.counter.count(text)
        assert count >= 1

    def test_count_messages(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        count = self.counter.count_messages(messages)
        assert count > 0

    def test_estimate_cost(self):
        cost = self.counter.estimate_cost(1000, "gpt-4o")
        assert "input_cost_usd" in cost
        assert cost["input_cost_usd"] > 0


class TestTextCompressor:
    def setup_method(self):
        self.compressor = TextCompressor()

    def test_compress_polite_zh(self):
        text = "请帮我分析这段代码，谢谢"
        compressed = self.compressor.compress(text, level="light")
        # 礼貌用语应被去除
        assert len(compressed) <= len(text)

    def test_compress_empty(self):
        assert self.compressor.compress("") == ""

    def test_compress_levels(self):
        text = "请你帮我详细解释一下这个函数是做什么的，谢谢你的帮助。\n\n\n\n多余的空行"
        light = self.compressor.compress(text, level="light")
        moderate = self.compressor.compress(text, level="moderate")
        aggressive = self.compressor.compress(text, level="aggressive")
        # 压缩级别越高，结果应该越短（或相等）
        assert len(aggressive) <= len(moderate) + 10  # 允许小误差
        assert len(moderate) <= len(light) + 10

    def test_clean_whitespace(self):
        text = "line1\n\n\n\nline2"
        compressed = self.compressor.compress(text, level="light")
        assert "\n\n\n" not in compressed


class TestContextManager:
    def setup_method(self):
        self.manager = ContextManager()

    def test_prune_empty(self):
        assert self.manager.prune([]) == []

    def test_prune_keeps_recent(self):
        messages = [
            {"role": "user", "content": f"message {i}"}
            for i in range(20)
        ]
        pruned = self.manager.prune(messages, max_tokens=100, keep_last=3)
        # 最后 3 条应该被保留
        assert pruned[-1]["content"] == "message 19"
        assert pruned[-2]["content"] == "message 18"
        assert pruned[-3]["content"] == "message 17"

    def test_prune_keeps_system(self):
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        pruned = self.manager.prune(messages, max_tokens=1000)
        roles = [m["role"] for m in pruned]
        assert "system" in roles

    def test_prune_keeps_recent_when_budget_is_tight(self):
        messages = [
            {"role": "user", "content": "old context"},
            {"role": "assistant", "content": "older reply"},
            {"role": "user", "content": "recent short"},
            {"role": "assistant", "content": "latest"},
        ]
        budget = self.manager.counter.count_messages(messages[-2:])
        pruned = self.manager.prune(messages, max_tokens=budget, keep_last=2, keep_system=False)
        contents = [m["content"] for m in pruned]
        assert "recent short" in contents
        assert "latest" in contents

    def test_prune_prefers_important_early_messages(self):
        messages = [
            {"role": "user", "content": "small note"},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "Traceback: ValueError in parser.py line 9"},
            {"role": "assistant", "content": "investigating"},
            {"role": "user", "content": "recent question"},
            {"role": "assistant", "content": "recent answer"},
        ]
        budget = self.manager.counter.count_messages(messages[-2:]) + self.manager.counter.count_messages([messages[2]])
        pruned = self.manager.prune(messages, max_tokens=budget, keep_last=2, keep_system=False)
        contents = [m["content"] for m in pruned]
        assert "Traceback: ValueError in parser.py line 9" in contents

    def test_get_stats(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        stats = self.manager.get_stats(messages)
        assert "total_messages" in stats
        assert stats["total_messages"] == 2
        assert "total_tokens" in stats


class TestPromptOptimizer:
    def setup_method(self):
        self.optimizer = PromptOptimizer()

    def test_analyze_returns_dict(self):
        result = self.optimizer.analyze("请帮我分析这段代码，谢谢")
        assert "original_tokens" in result
        assert "optimized_tokens" in result
        assert "suggestions" in result
        assert "savings_pct" in result

    def test_optimize_injects_system(self):
        messages = [{"role": "user", "content": "Hello"}]
        optimized = self.optimizer.optimize(messages, inject_concise=True)
        roles = [m["role"] for m in optimized]
        assert "system" in roles

    def test_optimize_no_inject(self):
        messages = [{"role": "user", "content": "Hello"}]
        optimized = self.optimizer.optimize(messages, inject_concise=False)
        roles = [m["role"] for m in optimized]
        assert "system" not in roles


class TestSmartFileReader:
    def setup_method(self):
        self.reader = SmartFileReader()

    def test_python_signatures_keep_source_order(self, tmp_path):
        file_path = tmp_path / "sample.py"
        file_path.write_text(
            'class Greeter:\n'
            '    """Greeter docs."""\n'
            '\n'
            '    def hello(self, name):\n'
            '        return f"hi {name}"\n'
            '\n'
            'def top_level(x, y):\n'
            '    """Top docs."""\n'
            '    return x + y\n',
            encoding="utf-8",
        )

        result = self.reader.read(file_path, mode="signatures")

        assert "class Greeter:" in result
        assert "def hello(self, name):" in result
        assert "def top_level(x, y):" in result
        assert result.index("class Greeter:") < result.index("def top_level(x, y):")

    def test_diff_mode_uses_unified_diff(self, tmp_path):
        file_path = tmp_path / "sample.py"
        file_path.write_text("a = 1\nb = 3\n", encoding="utf-8")

        result = self.reader.read(
            file_path,
            mode="diff",
            previous="a = 1\nb = 2\n",
        )

        assert "--- previous" in result
        assert "+++ current" in result
        assert "-b = 2" in result
        assert "+b = 3" in result
