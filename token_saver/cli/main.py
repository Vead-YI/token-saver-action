"""
CLI 入口
提供命令行工具 `token-saver`
"""

import json
import sys
from pathlib import Path

import click

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    _RICH = True
except ImportError:
    _RICH = False

from ..core.token_counter import TokenCounter
from ..core.compressor import TextCompressor
from ..core.context_manager import ContextManager
from ..strategies.file_reader import SmartFileReader
from ..strategies.prompt_optimizer import PromptOptimizer

console = Console() if _RICH else None


def _print(msg: str, style: str = ""):
    if _RICH and console:
        console.print(msg, style=style)
    else:
        print(msg)


@click.group()
@click.version_option(version="0.1.0", prog_name="token-saver")
def cli():
    """🪙 节省Token行动 — 帮你在使用 AI 时节约 Token"""
    pass


@cli.command()
@click.argument("text", required=False)
@click.option("--file", "-f", type=click.Path(exists=True), help="从文件读取文本")
@click.option("--model", "-m", default="gpt-4o", help="模型名称（影响计数精度）")
def count(text, file, model):
    """统计文本的 Token 数量"""
    if file:
        text = Path(file).read_text(encoding="utf-8")
    elif not text:
        text = click.get_text_stream("stdin").read()

    counter = TokenCounter(model=model)
    tokens = counter.count(text)
    chars = len(text)
    cost = counter.estimate_cost(tokens, model)

    if _RICH:
        table = Table(title=f"Token 统计 ({model})")
        table.add_column("指标", style="cyan")
        table.add_column("数值", style="green")
        table.add_row("字符数", f"{chars:,}")
        table.add_row("Token 数", f"{tokens:,}")
        table.add_row("字符/Token 比", f"{chars/max(tokens,1):.2f}")
        table.add_row("输入费用估算", f"${cost['input_cost_usd']:.6f}")
        console.print(table)
    else:
        print(f"字符数: {chars}")
        print(f"Token 数: {tokens}")
        print(f"输入费用估算: ${cost['input_cost_usd']:.6f}")


@cli.command()
@click.argument("text", required=False)
@click.option("--file", "-f", type=click.Path(exists=True), help="从文件读取")
@click.option("--level", "-l", default="moderate",
              type=click.Choice(["light", "moderate", "aggressive"]),
              help="压缩级别")
@click.option("--model", "-m", default="gpt-4o", help="模型名称")
def compress(text, file, level, model):
    """压缩 Prompt，去除冗余内容"""
    if file:
        text = Path(file).read_text(encoding="utf-8")
    elif not text:
        text = click.get_text_stream("stdin").read()

    counter = TokenCounter(model=model)
    compressor = TextCompressor()

    original_tokens = counter.count(text)
    compressed = compressor.compress(text, level=level)
    compressed_tokens = counter.count(compressed)
    savings = original_tokens - compressed_tokens
    savings_pct = (1 - compressed_tokens / max(original_tokens, 1)) * 100

    if _RICH:
        console.print(Panel(compressed, title="压缩结果", border_style="green"))
        console.print(
            f"[cyan]原始:[/cyan] {original_tokens} tokens → "
            f"[green]压缩后:[/green] {compressed_tokens} tokens "
            f"[yellow](节省 {savings} tokens, {savings_pct:.1f}%)[/yellow]"
        )
    else:
        print(compressed)
        print(f"\n原始: {original_tokens} tokens → 压缩后: {compressed_tokens} tokens (节省 {savings_pct:.1f}%)")


@cli.command()
@click.argument("filepath", type=click.Path(exists=True))
@click.option("--mode", "-m", default="signatures",
              type=click.Choice(["full", "signatures", "summary", "keywords", "head_tail"]),
              help="读取模式")
@click.option("--keywords", "-k", multiple=True, help="关键词（mode=keywords 时使用）")
@click.option("--context", "-c", default=3, help="关键词上下文行数")
def read(filepath, mode, keywords, context):
    """智能读取文件，只输出关键部分"""
    reader = SmartFileReader()
    result = reader.read(
        filepath,
        mode=mode,
        keywords=list(keywords) if keywords else None,
        context_lines=context,
    )

    counter = TokenCounter()
    full_content = Path(filepath).read_text(encoding="utf-8", errors="replace")
    full_tokens = counter.count(full_content)
    result_tokens = counter.count(result)

    if _RICH:
        console.print(Panel(result, title=f"{filepath} [{mode}]", border_style="blue"))
        console.print(
            f"[cyan]完整文件:[/cyan] {full_tokens} tokens → "
            f"[green]读取结果:[/green] {result_tokens} tokens "
            f"[yellow](节省 {(1-result_tokens/max(full_tokens,1))*100:.1f}%)[/yellow]"
        )
    else:
        print(result)
        print(f"\n完整: {full_tokens} tokens → 读取: {result_tokens} tokens")


@cli.command()
@click.argument("history_file", type=click.Path(exists=True))
@click.option("--max-tokens", "-t", default=4000, help="最大 token 预算")
@click.option("--keep-last", "-k", default=4, help="强制保留最后 N 条消息")
@click.option("--output", "-o", help="输出文件路径（默认打印到 stdout）")
def prune(history_file, max_tokens, keep_last, output):
    """裁剪对话历史到 token 预算内"""
    messages = json.loads(Path(history_file).read_text(encoding="utf-8"))

    counter = TokenCounter()
    manager = ContextManager(counter=counter)

    original_tokens = counter.count_messages(messages)
    pruned = manager.prune(messages, max_tokens=max_tokens, keep_last=keep_last)
    pruned_tokens = counter.count_messages(pruned)

    result_json = json.dumps(pruned, ensure_ascii=False, indent=2)

    if output:
        Path(output).write_text(result_json, encoding="utf-8")
        _print(f"✅ 已保存到 {output}", "green")
    else:
        print(result_json)

    _print(
        f"消息数: {len(messages)} → {len(pruned)} | "
        f"Tokens: {original_tokens} → {pruned_tokens} "
        f"(节省 {(1-pruned_tokens/max(original_tokens,1))*100:.1f}%)"
    )


@cli.command()
@click.argument("text", required=False)
@click.option("--file", "-f", type=click.Path(exists=True), help="从文件读取")
@click.option("--model", "-m", default="gpt-4o", help="模型名称")
def analyze(text, file, model):
    """分析 Prompt 并给出优化建议"""
    if file:
        text = Path(file).read_text(encoding="utf-8")
    elif not text:
        text = click.get_text_stream("stdin").read()

    optimizer = PromptOptimizer(model=model)
    result = optimizer.analyze(text)

    if _RICH:
        console.print(f"\n[bold]📊 Prompt 分析报告[/bold]")
        console.print(f"原始 Tokens: [red]{result['original_tokens']}[/red]")
        console.print(f"优化后 Tokens: [green]{result['optimized_tokens']}[/green]")
        console.print(
            f"可节省: [yellow]{result['savings']} tokens ({result['savings_pct']}%)[/yellow]\n"
        )

        if result["suggestions"]:
            console.print("[bold]💡 优化建议:[/bold]")
            for s in result["suggestions"]:
                console.print(f"  • [{s['type']}] {s['description']} (预计节省 {s['savings_estimate']})")

        console.print(Panel(result["optimized_preview"], title="优化预览", border_style="green"))
    else:
        print(f"原始: {result['original_tokens']} tokens")
        print(f"优化后: {result['optimized_tokens']} tokens (节省 {result['savings_pct']}%)")
        for s in result["suggestions"]:
            print(f"  - {s['description']}")
        print("\n优化预览:")
        print(result["optimized_preview"])


if __name__ == "__main__":
    cli()
