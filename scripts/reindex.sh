#!/bin/bash
# Jarvis - 重建本地知识库索引（实现）
# 用法: bash scripts/reindex.sh
# 将 knowledge/*.md 与 analyses / memory 切分写入本地向量或 Milvus

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ ! -x "$ROOT/backend/.venv/bin/python" ]; then
  echo "后端虚拟环境未就绪，请先: bash start.sh 或手动创建 backend/.venv"
  exit 1
fi

cd "$ROOT/backend"
export PYTHONPATH="$ROOT/backend"
echo "正在重建知识库索引..."
"$ROOT/backend/.venv/bin/python" -m app.scripts.reindex_kb
echo ""
echo "完成。VECTOR_BACKEND=local 时写入 data/vectordb/local_kb.json；=milvus 时写入 Docker Milvus。"
echo "若后端已在运行，可直接继续对话，无需重启。"
