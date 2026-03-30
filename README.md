# 🪙 节省Token行动 (Token Saver Action)

> 帮助用户在使用 AI、AI Agent 和 OpenClaw 时大幅节约 Token 消耗

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

---

## 🎯 项目目标

在与 AI 交互时，Token 是核心成本。本项目提供一套**实用工具集**，通过多种策略帮助用户：

- 📉 **减少 Prompt 冗余** — 自动压缩、去重、精简输入
- 🧠 **智能上下文管理** — 只保留真正有用的对话历史
- 📦 **文件内容优化** — 读取代码/文档时只传递关键部分
- 💬 **输出长度控制** — 引导 AI 给出简洁回答
- 📊 **Token 用量统计** — 可视化你的消耗，找到节省点

---

## 🏗️ 架构概览

```
token-saver-action/
├── core/                    # 核心压缩引擎
│   ├── compressor.py        # 文本压缩器（去冗余、摘要）
│   ├── context_manager.py   # 对话上下文管理
│   └── token_counter.py     # Token 计数工具
├── strategies/              # 节省策略模块
│   ├── prompt_optimizer.py  # Prompt 优化
│   ├── file_reader.py       # 智能文件读取（只读关键部分）
│   ├── history_pruner.py    # 历史对话裁剪
│   └── output_controller.py # 输出长度控制
├── integrations/            # 集成适配器
│   ├── openclaw/            # OpenClaw Skill 集成
│   ├── langchain/           # LangChain 集成
│   └── openai/              # OpenAI API 直接集成
├── cli/                     # 命令行工具
│   └── main.py              # CLI 入口
├── examples/                # 使用示例
│   ├── basic_usage.py
│   ├── openclaw_skill.md
│   └── agent_workflow.py
├── tests/                   # 测试
├── docs/                    # 文档
│   ├── strategies.md        # 各策略详解
│   └── benchmarks.md        # 节省效果基准测试
├── pyproject.toml
└── README.md
```

---

## 🚀 快速开始

### 安装

```bash
pip install token-saver-action
```

或从源码安装：

```bash
git clone https://github.com/YOUR_USERNAME/token-saver-action
cd token-saver-action
pip install -e .
```

### 基础用法

```python
from token_saver import TokenSaver

saver = TokenSaver()

# 压缩一段 Prompt
original = """
请你帮我分析一下这段代码，告诉我它是做什么的，有没有什么问题，
如果有问题的话请帮我修复，另外也请告诉我有没有可以优化的地方，
谢谢你的帮助，我非常感激。

def add(a, b):
    return a + b
"""

compressed = saver.compress_prompt(original)
print(f"原始: {saver.count_tokens(original)} tokens")
print(f"压缩后: {saver.count_tokens(compressed)} tokens")
print(compressed)
```

### CLI 用法

```bash
# 分析一个文件，只输出关键部分
token-saver read --file mycode.py --mode signatures

# 压缩 Prompt
token-saver compress "你的很长的prompt..."

# 统计 Token 用量
token-saver count --file prompt.txt

# 优化对话历史（裁剪不重要的轮次）
token-saver prune --history chat_history.json --keep-last 5
```

---

## 📐 核心策略

### 1. Prompt 优化 (`strategies/prompt_optimizer.py`)

| 策略 | 说明 | 节省估算 |
|------|------|---------|
| 去除礼貌用语 | 删除"请"、"谢谢"、"麻烦"等 | 5-15% |
| 合并重复意图 | 将多个相似要求合并为一句 | 10-30% |
| 结构化指令 | 用列表替代长段落描述 | 15-25% |
| 移除冗余上下文 | 删除 AI 已知的背景信息 | 20-40% |

### 2. 智能文件读取 (`strategies/file_reader.py`)

不再把整个文件塞进 context，而是：
- **签名模式**：只读函数/类签名
- **摘要模式**：提取注释和文档字符串
- **差异模式**：只读与上次不同的部分
- **关键词模式**：只读包含目标关键词的行

### 3. 历史裁剪 (`strategies/history_pruner.py`)

- 保留最近 N 轮对话
- 对早期对话做摘要压缩
- 移除重复/无效的 AI 回复
- 基于相关性评分保留重要轮次

### 4. 输出控制 (`strategies/output_controller.py`)

在 System Prompt 中注入简洁性指令，引导 AI：
- 直接给答案，不解释显而易见的事
- 用代码替代文字描述
- 避免重复用户的问题

---

## 🔌 OpenClaw 集成

将 `integrations/openclaw/` 下的文件复制到你的 OpenClaw skills 目录，即可作为 Skill 使用：

```
# 在 OpenClaw 中使用
帮我压缩这个 prompt：[你的 prompt]
```

详见 [OpenClaw 集成文档](examples/openclaw_skill.md)。

---

## 📊 基准测试

在典型使用场景下的节省效果（详见 [benchmarks.md](docs/benchmarks.md)）：

| 场景 | 原始 Tokens | 优化后 | 节省 |
|------|------------|--------|------|
| 代码审查请求 | 850 | 420 | **51%** |
| 长文档问答 | 3200 | 980 | **69%** |
| 多轮对话（20轮） | 12000 | 3800 | **68%** |
| Agent 工具调用 | 2400 | 890 | **63%** |

---

## 🤝 参考项目

- [lean-ctx](https://github.com/yvgude/lean-ctx) — Shell Hook + MCP 上下文优化
- [microsoft/LLMLingua](https://github.com/microsoft/LLMLingua) — 学术级 Prompt 压缩
- [LLMLingua-2](https://aclanthology.org/2024.findings-acl.57/) — 数据蒸馏压缩方法

---

## 📄 License

MIT License — 自由使用、修改、分发。
