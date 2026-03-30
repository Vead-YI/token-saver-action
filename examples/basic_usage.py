"""
基础用法示例
"""

from token_saver import TokenSaver
from token_saver.strategies.file_reader import SmartFileReader
from token_saver.strategies.prompt_optimizer import PromptOptimizer

# ============================================================
# 示例 1: 压缩一个典型的中文 Prompt
# ============================================================

saver = TokenSaver()

original_prompt = """
你好，请你帮我分析一下这段代码，告诉我它是做什么的，有没有什么问题，
如果有问题的话请帮我修复，另外也请告诉我有没有可以优化的地方，
非常感谢你的帮助，我非常感激。

def calculate_average(numbers):
    total = 0
    for num in numbers:
        total = total + num
    average = total / len(numbers)
    return average
"""

compressed = saver.compress_prompt(original_prompt)
original_tokens = saver.count_tokens(original_prompt)
compressed_tokens = saver.count_tokens(compressed)

print("=" * 50)
print("示例 1: Prompt 压缩")
print("=" * 50)
print(f"原始 ({original_tokens} tokens):\n{original_prompt}")
print(f"\n压缩后 ({compressed_tokens} tokens):\n{compressed}")
print(f"\n节省: {original_tokens - compressed_tokens} tokens ({(1-compressed_tokens/original_tokens)*100:.1f}%)")


# ============================================================
# 示例 2: 优化对话历史
# ============================================================

messages = [
    {"role": "system", "content": "你是一个 Python 编程助手。"},
    {"role": "user", "content": "什么是列表推导式？"},
    {"role": "assistant", "content": "列表推导式是 Python 中创建列表的简洁方式...（很长的回答）" * 20},
    {"role": "user", "content": "能给我一个例子吗？"},
    {"role": "assistant", "content": "[x**2 for x in range(10)]"},
    {"role": "user", "content": "谢谢！那字典推导式呢？"},
    {"role": "assistant", "content": "字典推导式类似...（很长的回答）" * 20},
    {"role": "user", "content": "好的，现在帮我写一个函数"},
]

print("\n" + "=" * 50)
print("示例 2: 对话历史优化")
print("=" * 50)

original_tokens = saver.count_tokens(str(messages))
optimized = saver.optimize_history(messages, max_tokens=500)
optimized_tokens = saver.count_tokens(str(optimized))

print(f"原始消息数: {len(messages)}, 估算 tokens: {original_tokens}")
print(f"优化后消息数: {len(optimized)}, 估算 tokens: {optimized_tokens}")
print(f"保留的消息角色: {[m['role'] for m in optimized]}")


# ============================================================
# 示例 3: 智能文件读取
# ============================================================

import tempfile, os

# 创建一个示例 Python 文件
sample_code = '''"""
数学工具模块
提供常用数学计算函数
"""

import math


def calculate_average(numbers: list) -> float:
    """计算平均值"""
    if not numbers:
        raise ValueError("列表不能为空")
    return sum(numbers) / len(numbers)


def calculate_std(numbers: list) -> float:
    """计算标准差"""
    avg = calculate_average(numbers)
    variance = sum((x - avg) ** 2 for x in numbers) / len(numbers)
    return math.sqrt(variance)


class Statistics:
    """统计分析类"""

    def __init__(self, data: list):
        self.data = data
        self._cache = {}

    def mean(self) -> float:
        """均值"""
        if "mean" not in self._cache:
            self._cache["mean"] = calculate_average(self.data)
        return self._cache["mean"]

    def std(self) -> float:
        """标准差"""
        return calculate_std(self.data)

    def summary(self) -> dict:
        """汇总统计"""
        return {
            "count": len(self.data),
            "mean": self.mean(),
            "std": self.std(),
            "min": min(self.data),
            "max": max(self.data),
        }
'''

with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
    f.write(sample_code)
    tmp_path = f.name

reader = SmartFileReader()
counter = saver.counter

print("\n" + "=" * 50)
print("示例 3: 智能文件读取")
print("=" * 50)

full_tokens = counter.count(sample_code)
print(f"完整文件: {full_tokens} tokens")

for mode in ["signatures", "summary"]:
    result = reader.read(tmp_path, mode=mode)
    result_tokens = counter.count(result)
    print(f"\n[{mode}] {result_tokens} tokens (节省 {(1-result_tokens/full_tokens)*100:.1f}%):")
    print(result)

os.unlink(tmp_path)


# ============================================================
# 示例 4: Prompt 分析
# ============================================================

print("\n" + "=" * 50)
print("示例 4: Prompt 分析与建议")
print("=" * 50)

optimizer = PromptOptimizer()
analysis = optimizer.analyze(original_prompt)

print(f"原始: {analysis['original_tokens']} tokens")
print(f"可优化至: {analysis['optimized_tokens']} tokens (节省 {analysis['savings_pct']}%)")
print("\n优化建议:")
for s in analysis["suggestions"]:
    print(f"  [{s['type']}] {s['description']} — 预计节省 {s['savings_estimate']}")
