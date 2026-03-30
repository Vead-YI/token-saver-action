"""
智能文件读取器
不把整个文件塞进 context，只读取真正需要的部分
"""

from __future__ import annotations

import ast
import difflib
import re
from pathlib import Path


class SmartFileReader:
    """
    智能文件读取器

    支持多种读取模式：
    - full: 完整读取（默认，不节省）
    - signatures: 只读函数/类签名
    - summary: 提取文档字符串和注释
    - keywords: 只读包含关键词的行（±上下文）
    - diff: 只读与上次不同的部分（需要提供 previous）
    - head_tail: 读取文件头尾（适合配置文件）
    """

    def read(
        self,
        path: str | Path,
        mode: str = "full",
        keywords: list[str] | None = None,
        context_lines: int = 3,
        max_lines: int | None = None,
        previous: str | None = None,
    ) -> str:
        """
        读取文件内容

        Args:
            path: 文件路径
            mode: 读取模式
            keywords: 关键词列表（mode="keywords" 时使用）
            context_lines: 关键词模式下，关键词前后保留的行数
            max_lines: 最大行数限制
            previous: 上次的文件内容（mode="diff" 时使用）

        Returns:
            处理后的文件内容字符串
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")

        content = path.read_text(encoding="utf-8", errors="replace")

        if mode == "full":
            result = content
        elif mode == "signatures":
            result = self._extract_signatures(content, path.suffix)
        elif mode == "summary":
            result = self._extract_summary(content, path.suffix)
        elif mode == "keywords":
            if not keywords:
                raise ValueError("mode='keywords' 需要提供 keywords 参数")
            result = self._extract_by_keywords(content, keywords, context_lines)
        elif mode == "diff":
            if previous is None:
                result = content
            else:
                result = self._extract_diff(previous, content)
        elif mode == "head_tail":
            result = self._extract_head_tail(content, lines=50)
        else:
            raise ValueError(f"未知的读取模式: {mode}")

        if max_lines:
            result = self._truncate_lines(result, max_lines)

        return result

    def _extract_signatures(self, content: str, suffix: str) -> str:
        """提取函数/类签名"""
        if suffix == ".py":
            return self._python_signatures(content)
        elif suffix in (".js", ".ts", ".jsx", ".tsx"):
            return self._js_signatures(content)
        else:
            # 通用：提取看起来像函数定义的行
            return self._generic_signatures(content)

    def _python_signatures(self, content: str) -> str:
        """提取 Python 函数和类签名"""
        lines = []
        try:
            tree = ast.parse(content)
            source_lines = content.splitlines()
            self._collect_python_signatures(tree.body, source_lines, lines)
        except SyntaxError:
            # 解析失败，退回正则
            return self._generic_signatures(content)

        return "\n".join(lines) if lines else content[:500]

    def _js_signatures(self, content: str) -> str:
        """提取 JS/TS 函数签名"""
        patterns = [
            r"^(export\s+)?(async\s+)?function\s+\w+[^{]*",
            r"^(export\s+)?(const|let|var)\s+\w+\s*=\s*(async\s+)?\([^)]*\)\s*=>",
            r"^(export\s+)?(abstract\s+)?class\s+\w+[^{]*",
            r"^\s+(async\s+)?\w+\s*\([^)]*\)\s*[:{]",
        ]
        lines = content.splitlines()
        result = []
        for line in lines:
            for pattern in patterns:
                if re.match(pattern, line.strip()):
                    result.append(line)
                    break
        return "\n".join(result) if result else content[:500]

    def _generic_signatures(self, content: str) -> str:
        """通用签名提取"""
        patterns = [
            r"^\s*(def |class |function |async function |export |public |private |protected )",
        ]
        lines = content.splitlines()
        result = []
        for line in lines:
            for pattern in patterns:
                if re.match(pattern, line):
                    result.append(line)
                    break
        return "\n".join(result) if result else content[:500]

    def _extract_summary(self, content: str, suffix: str) -> str:
        """提取文档字符串和注释"""
        lines = content.splitlines()
        result = []
        in_docstring = False
        docstring_char = None

        for line in lines:
            stripped = line.strip()

            # 检测文档字符串
            if not in_docstring:
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    in_docstring = True
                    docstring_char = stripped[:3]
                    result.append(line)
                    if stripped.count(docstring_char) >= 2 and len(stripped) > 3:
                        in_docstring = False
                elif stripped.startswith("#") or stripped.startswith("//"):
                    result.append(line)
            else:
                result.append(line)
                if docstring_char and docstring_char in stripped[1:]:
                    in_docstring = False

        return "\n".join(result) if result else content[:300]

    def _extract_by_keywords(
        self, content: str, keywords: list[str], context_lines: int
    ) -> str:
        """提取包含关键词的行及其上下文"""
        lines = content.splitlines()
        matched_indices = set()

        for i, line in enumerate(lines):
            for kw in keywords:
                if kw.lower() in line.lower():
                    # 添加上下文行
                    for j in range(
                        max(0, i - context_lines), min(len(lines), i + context_lines + 1)
                    ):
                        matched_indices.add(j)
                    break

        if not matched_indices:
            return f"[未找到关键词: {', '.join(keywords)}]"

        result = []
        prev_idx = -2
        for idx in sorted(matched_indices):
            if idx > prev_idx + 1:
                result.append("...")
            result.append(f"{idx + 1:4d} | {lines[idx]}")
            prev_idx = idx

        return "\n".join(result)

    def _extract_diff(self, previous: str, current: str) -> str:
        """提取两个版本之间的差异"""
        diff_lines = list(
            difflib.unified_diff(
                previous.splitlines(),
                current.splitlines(),
                fromfile="previous",
                tofile="current",
                lineterm="",
                n=2,
            )
        )

        if not diff_lines:
            return "[文件无变化]"
        return "\n".join(diff_lines[:200])

    def _extract_head_tail(self, content: str, lines: int = 50) -> str:
        """读取文件头尾"""
        all_lines = content.splitlines()
        if len(all_lines) <= lines * 2:
            return content

        head = all_lines[:lines]
        tail = all_lines[-lines:]
        middle_count = len(all_lines) - lines * 2

        return (
            "\n".join(head)
            + f"\n\n... [中间省略 {middle_count} 行] ...\n\n"
            + "\n".join(tail)
        )

    def _collect_python_signatures(
        self,
        nodes: list[ast.stmt],
        source_lines: list[str],
        output: list[str],
    ) -> None:
        """按源码顺序收集类和函数签名。"""
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                start = min(node.lineno - 1, len(source_lines) - 1)
                end_line = start
                if node.body:
                    end_line = max(start, node.body[0].lineno - 1)
                signature = "\n".join(source_lines[start:end_line]).rstrip()
                output.append(signature if signature else source_lines[start])
                docstring = ast.get_docstring(node)
                if docstring:
                    output.append(f'    """{docstring[:100]}"""')
                output.append("")
                self._collect_python_signatures(node.body, source_lines, output)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = min(node.lineno - 1, len(source_lines) - 1)
                end_line = start
                if node.body:
                    end_line = max(start, node.body[0].lineno - 1)
                signature = "\n".join(source_lines[start:end_line]).rstrip()
                output.append(signature if signature else source_lines[start])
                docstring = ast.get_docstring(node)
                if docstring:
                    output.append('    """' + docstring[:100] + '"""')
                output.append("")

    def _truncate_lines(self, content: str, max_lines: int) -> str:
        """统一处理输出截断，避免在提取前破坏结构。"""
        lines = content.splitlines()
        if len(lines) <= max_lines:
            return content
        return "\n".join(lines[:max_lines]) + f"\n... (已截断，共 {len(lines)} 行)"
