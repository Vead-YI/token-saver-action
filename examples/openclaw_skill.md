# OpenClaw 集成指南

本文档说明如何在 OpenClaw 中使用 `token-saver-action`。

## 安装

```bash
cd ~/.qclaw/workspace/token-saver-action
pip install -e .
```

## 在 OpenClaw Skill 中使用

### 方式 1：在 Skill 的 Python 脚本中调用

```python
from token_saver import TokenSaver
from token_saver.strategies.file_reader import SmartFileReader

saver = TokenSaver()
reader = SmartFileReader()

# 读取代码文件时，只传签名
code_context = reader.read("myproject/main.py", mode="signatures")

# 压缩用户的 Prompt
compressed_prompt = saver.compress_prompt(user_input)
```

### 方式 2：在 OpenClaw 工具调用前预处理

在调用 `read` 工具读取大文件前，先用 `SmartFileReader` 提取关键部分：

```python
# 不要这样（会消耗大量 token）：
# content = read("large_file.py")  # 可能 5000+ tokens

# 这样更好：
from token_saver.strategies.file_reader import SmartFileReader
reader = SmartFileReader()
content = reader.read("large_file.py", mode="signatures")  # 通常 < 500 tokens
```

### 方式 3：对话历史管理

在长对话中，定期裁剪历史：

```python
from token_saver import TokenSaver

saver = TokenSaver()

# 在每次 AI 调用前
messages = get_current_history()
if saver.count_tokens(str(messages)) > 3000:
    messages = saver.optimize_history(messages, max_tokens=2000)
```

## 推荐的 System Prompt 注入

在你的 OpenClaw Skill 的 System Prompt 中加入：

```
回答要求：
- 直接给出答案，不重复我的问题
- 代码用代码块，不用文字描述代码
- 省略显而易见的解释
- 如无必要，不加免责声明
```

这可以减少 AI 输出的冗余内容，节省 output token。

## 节省效果参考

| 场景 | 操作 | 预期节省 |
|------|------|---------|
| 读取 Python 文件 | `mode="signatures"` | 70-90% |
| 读取配置文件 | `mode="head_tail"` | 50-80% |
| 压缩中文 Prompt | `level="moderate"` | 15-30% |
| 裁剪长对话 | `max_tokens=2000` | 40-70% |
| 注入简洁指令 | System Prompt 注入 | 10-20% output |
