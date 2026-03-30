---
name: token-saver
description: "Token 节省工具集。在需要节约 AI Token 消耗时使用此技能。触发场景：(1) 用户说'帮我压缩这个 prompt'、'节省 token'、'优化输入' (2) 需要读取大文件但只关心部分内容 (3) 对话历史太长需要裁剪 (4) 想知道某段文本消耗多少 token (5) 想分析 prompt 有哪些可以优化的地方。支持工具：count_tokens、compress_prompt、read_file_smart、optimize_history、analyze_prompt、get_concise_injection、batch_count。"
metadata: {"openclaw": {"category": "productivity", "type": "mcp"}}
---

# token-saver

帮助用户在使用 AI、AI Agent 和 OpenClaw 时节约 Token 消耗。

## 配置

首次使用前运行：

```bash
bash setup.sh
```

## 可用工具

### `count_tokens` — 统计 Token 数量

```
统计这段文字消耗多少 token：[文字]
```

### `compress_prompt` — 压缩 Prompt

```
帮我压缩这个 prompt：[prompt 内容]
```

压缩级别：
- `light`：保守，只去礼貌用语
- `moderate`：推荐，去冗余 + 合并重复意图（默认）
- `aggressive`：最大压缩

### `read_file_smart` — 智能读取文件

```
用 signatures 模式读取 /path/to/file.py
```

模式说明：
- `signatures`：只读函数/类签名，节省 70-90%（推荐代码文件）
- `summary`：只读注释和文档字符串
- `keywords`：只读包含关键词的行
- `head_tail`：读取文件头尾（适合配置文件）

### `optimize_history` — 裁剪对话历史

传入 JSON 格式的消息列表，自动裁剪到 token 预算内。

### `analyze_prompt` — 分析优化建议

分析 Prompt 中的冗余，给出具体节省建议和优化预览。

### `get_concise_injection` — 获取简洁性指令

获取可注入 System Prompt 的简洁性指令，减少 AI 输出 15-25%。

### `batch_count` — 批量统计

批量统计多段文本的 Token 消耗，找出最大消耗点。

## 典型节省效果

| 场景 | 操作 | 节省 |
|------|------|------|
| 读取 Python 文件 | `read_file_smart` signatures | 70-90% |
| 压缩中文 Prompt | `compress_prompt` moderate | 15-30% |
| 裁剪长对话 | `optimize_history` | 40-70% |
| 注入简洁指令 | `get_concise_injection` | 15-25% 输出 |
