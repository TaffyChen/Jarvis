#!/bin/bash
# 启动 Jarvis MCP Server（stdio）。供 Cursor / Claude Desktop 配置使用。
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
export PYTHONPATH="$ROOT/backend"
exec "$ROOT/backend/.venv/bin/python" -m app.mcp
