# 节省策略详解

## 策略 1：Prompt 压缩

### 原理

用户在写 Prompt 时，往往包含大量对 AI 来说无意义的内容：

- **礼貌用语**：AI 不需要"请"、"谢谢"、"麻烦"来理解你的意图
- **冗余引导语**："你能帮我..."、"我想让你..."都是废话
- **重复意图**：同一个要求用不同方式说了两遍
- **过度背景**：AI 已经知道的事情不需要再解释

### 实现

`TextCompressor` 现在会先按 Markdown 代码块切分，再分别处理自然语言与代码：

- 自然语言部分：去礼貌用语、去引导语、合并重复意图、去重列表项
- 代码块部分：默认尽量保持原样，`aggressive` 级别下再清理明显冗余注释和空行
- 混合 Prompt：避免把代码片段误当成普通文本去压缩

分三个级别：

| 级别 | 操作 | 适用场景 |
|------|------|---------|
| `light` | 去礼貌用语 + 清理空白 | 保守，不改变语义 |
| `moderate` | light + 去引导语 + 去重 | 日常使用推荐 |
| `aggressive` | moderate + 压缩代码注释 + 缩短指令 | 最大节省，可能轻微改变表达 |

---

## 策略 2：智能文件读取

### 原理

把整个文件塞进 context 是最大的 token 浪费来源之一。
大多数情况下，AI 只需要文件的一部分。

### 读取模式

#### `signatures` 模式（推荐用于代码文件）

只提取函数/类签名和文档字符串。

```python
# 原始文件：500 行，约 3000 tokens
# signatures 模式：约 50 行，约 300 tokens（节省 90%）
```

#### `summary` 模式

只提取注释和文档字符串，了解文件的"意图"而不是实现。

#### `keywords` 模式

只读包含特定关键词的行及其上下文。适合在大文件中定位特定功能。

```bash
token-saver read myfile.py --mode keywords --keywords "error" "exception"
```

#### `diff` 模式

只读与上次不同的部分。适合迭代修改场景，避免重复传递未变化的代码。

#### `head_tail` 模式

读取文件头尾各 50 行。适合配置文件、日志文件。

---

## 策略 3：对话历史裁剪

### 原理

随着对话进行，历史消息会不断累积。但 AI 主要依赖最近的上下文，
早期的对话往往不再相关。

### 算法

1. 始终保留 system prompt
2. 始终保留最近 N 轮（默认 4 轮）
3. 优先整体保留最近 N 条；预算不足时按最近优先回退
4. 对更早的消息做粗粒度重要性评分，优先保留报错、约束、需求、问题等高价值内容
5. 超出预算的早期消息被丢弃，或替换为摘要占位符

### 进阶：摘要压缩

对于需要保留早期上下文的场景，可以将早期对话压缩为摘要：

```python
manager = ContextManager()
messages_with_summary = manager.summarize_old_messages(messages, keep_last=6)
# 然后用 AI 生成实际摘要，替换占位符
```

---

## 策略 4：输出控制

### 原理

AI 的输出 token 通常比输入贵 3-5 倍。通过 `OutputController`
在 System Prompt 中注入简洁性指令和回答预算，可以显著减少输出长度。

### 注入内容

```
回答要求：
- 直接给出答案，不重复我的问题
- 代码用代码块，不用文字描述代码
- 省略显而易见的解释
- 如无必要，不加免责声明
```

### 效果

在测试中，注入简洁性指令后，AI 输出长度平均减少 15-25%，
且回答质量不受影响（有时反而更好，因为去掉了废话）。

### 附加预算控制

`OutputController` 还支持继续追加输出预算，例如：

```python
from token_saver.strategies.output_controller import OutputController

controller = OutputController(language="zh")
system_prompt = controller.apply_to_system(
    "你是一个代码助手。",
    max_sentences=6,
    prefer_bullets=True,
    require_code_first=True,
)
```

---

## 组合使用

最大节省效果来自组合使用多种策略：

```python
from token_saver import TokenSaver
from token_saver.strategies.file_reader import SmartFileReader
from token_saver.strategies.prompt_optimizer import PromptOptimizer

saver = TokenSaver()
reader = SmartFileReader()
optimizer = PromptOptimizer()

# 1. 读取文件时只取签名
code = reader.read("myfile.py", mode="signatures")

# 2. 压缩用户 Prompt
user_msg = saver.compress_prompt(f"分析这段代码：\n{code}")

# 3. 优化消息列表（注入简洁指令 + 裁剪历史）
messages = history + [{"role": "user", "content": user_msg}]
messages = optimizer.optimize(messages, inject_concise=True)
messages = saver.optimize_history(messages, max_tokens=3000)

# 4. 发送给 AI
response = ai_client.chat(messages)
```
