#!/bin/bash
# Setup script for token-saver MCP Skill
# 将 token-saver 注册为 OpenClaw/QClaw 可调用的 MCP 工具

set -e

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SKILL_DIR")"
SERVER_SCRIPT="$PROJECT_DIR/mcp_server/server.py"

echo "🪙 设置 token-saver MCP Skill..."
echo ""

# ── 1. 检查 Python ─────────────────────────────────────────────────────────────
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.9+"
    exit 1
fi
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✅ Python $PYTHON_VERSION"

# ── 2. 安装依赖 ────────────────────────────────────────────────────────────────
echo "📦 安装依赖..."
pip install -e "$PROJECT_DIR" -q
pip install "mcp[cli]" -q
echo "✅ 依赖安装完成"

# ── 3. 验证 server 可以启动 ────────────────────────────────────────────────────
echo "🧪 验证 MCP Server..."
if python3 -c "import sys; sys.path.insert(0,'$PROJECT_DIR'); from token_saver import TokenSaver; print('OK')" 2>/dev/null | grep -q "OK"; then
    echo "✅ token_saver 模块加载正常"
else
    echo "❌ token_saver 模块加载失败，请检查安装"
    exit 1
fi

# ── 4. 注册到 mcporter（如果可用）────────────────────────────────────────────
if command -v mcporter &> /dev/null; then
    echo "🔧 注册到 mcporter..."
    mcporter config add token-saver "python3 $SERVER_SCRIPT" --scope project 2>/dev/null || true
    echo "✅ mcporter 注册完成"
    echo ""
    mcporter list 2>/dev/null | grep -A1 "token-saver" || true
else
    echo "ℹ️  未找到 mcporter，跳过自动注册"
    echo "   如需通过 mcporter 使用，请先运行：npm install -g mcporter"
fi

# ── 5. 输出手动配置方式 ────────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────────────────────────────"
echo "🎉 设置完成！"
echo ""
echo "📋 手动配置方式（在 claude_desktop_config.json 或 OpenClaw 配置中添加）："
echo ""
echo '  "mcpServers": {'
echo '    "token-saver": {'
echo '      "command": "python3",'
echo "      \"args\": [\"$SERVER_SCRIPT\"]"
echo '    }'
echo '  }'
echo ""
echo "🚀 直接启动 MCP Server（测试用）："
echo "   python3 $SERVER_SCRIPT"
echo ""
echo "🔧 可用工具："
echo "   - count_tokens       统计 Token 数量"
echo "   - compress_prompt    压缩 Prompt（节省 15-40%）"
echo "   - read_file_smart    智能读取文件（节省 70-90%）"
echo "   - optimize_history   裁剪对话历史"
echo "   - analyze_prompt     分析并给出优化建议"
echo "   - get_concise_injection  获取简洁性指令"
echo "   - batch_count        批量统计 Token"
