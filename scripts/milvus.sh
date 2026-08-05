#!/bin/bash
# Jarvis 专用 Milvus（Docker standalone）
# 用法: bash scripts/milvus.sh up|down|status|wait

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT/deploy/milvus/compose.yml"
ENV_FILE="$ROOT/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "未找到 .env"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "未找到 docker，请先启动 Docker Desktop"
  exit 1
fi

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

cmd="${1:-status}"

case "$cmd" in
  up)
    echo "启动 jarvis-milvus（首次拉取镜像可能较慢）..."
    compose up -d
    bash "$0" wait
    ;;
  down)
    echo "停止 jarvis-milvus（数据卷会保留）..."
    compose down
    ;;
  status)
    docker ps -a --filter name=jarvis-milvus --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
    docker ps -a --filter name=jarvis-attu --format '{{.Names}}\t{{.Status}}\t{{.Ports}}'
    ;;
  wait)
    echo "等待 Milvus 就绪..."
    for i in $(seq 1 90); do
      status=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' jarvis-milvus 2>/dev/null || true)
      if [ "$status" = "healthy" ]; then
        echo "jarvis-milvus 已就绪"
        attu_port=$(grep -E '^ATTU_PORT=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
        attu_port="${attu_port:-18000}"
        echo "Attu UI: http://127.0.0.1:${attu_port}"
        exit 0
      fi
      if [ "$i" -eq 1 ] || [ $((i % 5)) -eq 0 ]; then
        echo "  状态: ${status:-starting} ($i/90)"
      fi
      sleep 2
    done
    echo "Milvus 启动超时，请查看: docker logs jarvis-milvus"
    docker logs --tail 50 jarvis-milvus || true
    exit 1
    ;;
  *)
    echo "用法: bash scripts/milvus.sh up|down|status|wait"
    exit 1
    ;;
esac
