"""
token-saver MCP Server
基于 FastMCP 构建，暴露 token 节省工具给 OpenClaw / QClaw 调用
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 尝试导入 FastMCP（MCP Python SDK）
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print(
        "错误：需要安装 MCP SDK\n"
        "请运行：pip install mcp",
        file=sys.stderr,
    )
    sys.exit(1)

# 导入 token_saver 核心模块
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from token_saver import TokenSaver
from token_saver.strategies.file_reader import SmartFileReader
from token_saver.strategies.prompt_optimizer import PromptOptimizer

# ── 初始化 MCP Server ──────────────────────────────────────────────────────────
mcp = FastMCP(
    name="token-saver",
    instructions="""
你现在可以使用 token-saver 工具集来节省 Token 消耗。

可用工具：
- count_tokens: 统计文本的 Token 数量
- compress_prompt: 压缩 Prompt，去除冗余内容
- read_file_smart: 智能读取文件（只读关键部分）
- optimize_history: 裁剪对话历史到 token 预算内
- analyze_prompt: 分析 Prompt 并给出优化建议
- get_concise_injection: 获取简洁性指令（注入到 System Prompt）

建议在每次 AI 调用前使用这些工具预处理输入，可节省 30-70% 的 Token。
""".strip(),
)

# ── 全局实例 ───────────────────────────────────────────────────────────────────
_saver = TokenSaver()
_reader = SmartFileReader()
_optimizer = PromptOptimizer(language="zh")


# ── Tool 1: 统计 Token ─────────────────────────────────────────────────────────
@mcp.tool()
def count_tokens(text: str, model: str = "gpt-4o") -> dict:
    """
    统计文本的 Token 数量和费用估算。

    Args:
        text: 要统计的文本
        model: 模型名称，影响计数精度（默认 gpt-4o）

    Returns:
        包含 tokens、chars、estimated_cost_usd 的字典
    """
    from token_saver.core.token_counter import TokenCounter
    counter = TokenCounter(model=model)
    tokens = counter.count(text)
    cost = counter.estimate_cost(tokens, model)
    return {
        "tokens": tokens,
        "chars": len(text),
        "chars_per_token": round(len(text) / max(tokens, 1), 2),
        "estimated_input_cost_usd": round(cost["input_cost_usd"], 8),
        "model": model,
    }


# ── Tool 2: 压缩 Prompt ────────────────────────────────────────────────────────
@mcp.tool()
def compress_prompt(
    text: str,
    level: str = "moderate",
    model: str = "gpt-4o",
) -> dict:
    """
    压缩 Prompt，自动去除礼貌用语、冗余引导语、重复内容等。

    Args:
        text: 原始 Prompt 文本
        level: 压缩级别
            - "light": 只去礼貌用语和多余空白（保守）
            - "moderate": 推荐，去冗余 + 合并重复意图
            - "aggressive": 最大压缩，适合 token 紧张场景
        model: 用于计算节省量的模型名称

    Returns:
        包含 compressed_text、original_tokens、compressed_tokens、savings_pct 的字典
    """
    from token_saver.core.token_counter import TokenCounter
    from token_saver.core.compressor import TextCompressor

    counter = TokenCounter(model=model)
    compressor = TextCompressor()

    original_tokens = counter.count(text)
    compressed = compressor.compress(text, level=level)
    compressed_tokens = counter.count(compressed)
    savings = original_tokens - compressed_tokens
    savings_pct = round((1 - compressed_tokens / max(original_tokens, 1)) * 100, 1)

    return {
        "compressed_text": compressed,
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "savings_tokens": savings,
        "savings_pct": savings_pct,
        "level_used": level,
    }


# ── Tool 3: 智能文件读取 ───────────────────────────────────────────────────────
@mcp.tool()
def read_file_smart(
    file_path: str,
    mode: str = "signatures",
    keywords: str = "",
    context_lines: int = 3,
    max_lines: int = 500,
) -> dict:
    """
    智能读取文件，只返回真正需要的部分，大幅减少 Token 消耗。

    Args:
        file_path: 文件路径（绝对路径或相对路径）
        mode: 读取模式
            - "signatures": 只读函数/类签名（推荐用于代码文件，节省 70-90%）
            - "summary": 只读文档字符串和注释（了解文件意图）
            - "keywords": 只读包含关键词的行（需配合 keywords 参数）
            - "head_tail": 读取文件头尾各 50 行（适合配置文件）
            - "full": 完整读取（不节省，仅用于小文件）
        keywords: 关键词列表，用逗号分隔（mode="keywords" 时使用）
            例如："error,exception,raise"
        context_lines: 关键词模式下，关键词前后保留的行数（默认 3）
        max_lines: 最大行数限制（默认 500）

    Returns:
        包含 content、original_tokens、result_tokens、savings_pct 的字典
    """
    from token_saver.core.token_counter import TokenCounter

    path = Path(file_path)
    if not path.exists():
        return {"error": f"文件不存在: {file_path}"}

    counter = TokenCounter()
    full_content = path.read_text(encoding="utf-8", errors="replace")
    full_tokens = counter.count(full_content)

    kw_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else None

    try:
        result = _reader.read(
            file_path,
            mode=mode,
            keywords=kw_list,
            context_lines=context_lines,
            max_lines=max_lines,
        )
    except Exception as e:
        return {"error": str(e)}

    result_tokens = counter.count(result)
    savings_pct = round((1 - result_tokens / max(full_tokens, 1)) * 100, 1)

    return {
        "content": result,
        "file_path": str(path.resolve()),
        "mode_used": mode,
        "original_tokens": full_tokens,
        "result_tokens": result_tokens,
        "savings_pct": savings_pct,
    }


# ── Tool 4: 优化对话历史 ───────────────────────────────────────────────────────
@mcp.tool()
def optimize_history(
    messages_json: str,
    max_tokens: int = 4000,
    keep_last: int = 4,
) -> dict:
    """
    裁剪对话历史到 token 预算内，保留最重要的消息。

    Args:
        messages_json: OpenAI 格式的消息列表（JSON 字符串）
            格式：[{"role": "user", "content": "..."}, ...]
        max_tokens: 最大 token 预算（默认 4000）
        keep_last: 强制保留最后 N 条消息（默认 4）

    Returns:
        包含 optimized_messages、original_count、optimized_count、savings_pct 的字典
    """
    from token_saver.core.context_manager import ContextManager
    from token_saver.core.token_counter import TokenCounter

    try:
        messages = json.loads(messages_json)
    except json.JSONDecodeError as e:
        return {"error": f"JSON 解析失败: {e}"}

    if not isinstance(messages, list):
        return {"error": "messages_json 必须是一个列表"}

    counter = TokenCounter()
    manager = ContextManager(counter=counter)

    original_tokens = counter.count_messages(messages)
    pruned = manager.prune(messages, max_tokens=max_tokens, keep_last=keep_last)
    pruned_tokens = counter.count_messages(pruned)
    savings_pct = round((1 - pruned_tokens / max(original_tokens, 1)) * 100, 1)

    return {
        "optimized_messages": pruned,
        "optimized_messages_json": json.dumps(pruned, ensure_ascii=False),
        "original_count": len(messages),
        "optimized_count": len(pruned),
        "original_tokens": original_tokens,
        "optimized_tokens": pruned_tokens,
        "savings_pct": savings_pct,
    }


# ── Tool 5: 分析 Prompt ────────────────────────────────────────────────────────
@mcp.tool()
def analyze_prompt(text: str, model: str = "gpt-4o") -> dict:
    """
    分析 Prompt 并给出具体的优化建议，包括可节省的 Token 数量。

    Args:
        text: 要分析的 Prompt 文本
        model: 模型名称

    Returns:
        包含 original_tokens、optimized_tokens、savings_pct、suggestions、optimized_preview 的字典
    """
    optimizer = PromptOptimizer(model=model, language="zh")
    return optimizer.analyze(text)


# ── Tool 6: 获取简洁性指令 ────────────────────────────────────────────────────
@mcp.tool()
def get_concise_injection(language: str = "zh") -> dict:
    """
    获取推荐的简洁性指令文本，注入到 System Prompt 可减少 AI 输出 15-25%。

    Args:
        language: 语言，"zh"（中文）或 "en"（英文）

    Returns:
        包含 injection_text 和使用说明的字典
    """
    from token_saver.strategies.prompt_optimizer import (
        CONCISE_SYSTEM_INJECTION_ZH,
        CONCISE_SYSTEM_INJECTION_EN,
    )

    text = CONCISE_SYSTEM_INJECTION_ZH if language == "zh" else CONCISE_SYSTEM_INJECTION_EN

    return {
        "injection_text": text,
        "language": language,
        "usage": "将此文本追加到你的 System Prompt 末尾，可引导 AI 给出更简洁的回答",
        "estimated_output_savings": "15-25%",
    }


# ── Tool 7: 批量统计 ───────────────────────────────────────────────────────────
@mcp.tool()
def batch_count(texts_json: str, model: str = "gpt-4o") -> dict:
    """
    批量统计多段文本的 Token 数量，适合分析对话历史各部分的消耗。

    Args:
        texts_json: 文本列表（JSON 字符串），格式：["text1", "text2", ...]
            或带标签的字典列表：[{"label": "system", "text": "..."}, ...]
        model: 模型名称

    Returns:
        包含每段文本统计和总计的字典
    """
    from token_saver.core.token_counter import TokenCounter

    try:
        texts = json.loads(texts_json)
    except json.JSONDecodeError as e:
        return {"error": f"JSON 解析失败: {e}"}

    counter = TokenCounter(model=model)
    results = []
    total = 0

    for item in texts:
        if isinstance(item, str):
            label = f"text_{len(results)+1}"
            text = item
        elif isinstance(item, dict):
            label = item.get("label", f"text_{len(results)+1}")
            text = item.get("text", "")
        else:
            continue

        tokens = counter.count(text)
        total += tokens
        results.append({
            "label": label,
            "tokens": tokens,
            "chars": len(text),
        })

    return {
        "items": results,
        "total_tokens": total,
        "model": model,
    }


# ── 入口 ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run()
