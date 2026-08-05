#!/bin/bash
# Jarvis - 一键关闭网页 + MySQL + Milvus/Attu
# 用法: bash stop-all.sh
# 数据卷会保留，不会删库。

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo ">>> 停止 Jarvis 网页"
bash "$ROOT/scripts/stop.sh" || true

if ! command -v docker >/dev/null 2>&1; then
  echo "未找到 docker，跳过容器停止"
  echo "全部关闭流程结束"
  exit 0
fi

echo ">>> 停止 MySQL"
if [ -f "$ROOT/.env" ]; then
  bash "$ROOT/scripts/mysql.sh" down || echo "MySQL 未运行或停止失败（可忽略）"
else
  echo "没有 .env，跳过 MySQL"
fi

echo ">>> 停止 Milvus / Attu"
if [ -f "$ROOT/.env" ]; then
  bash "$ROOT/scripts/milvus.sh" down || echo "Milvus/Attu 未运行或停止失败（可忽略）"
else
  echo "没有 .env，跳过 Milvus"
fi

echo ""
echo "Jarvis 网页 + MySQL + Milvus/Attu 已全部关闭（数据卷仍保留）"
