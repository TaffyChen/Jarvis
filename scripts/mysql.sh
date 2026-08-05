#!/bin/bash
# Jarvis 专用 MySQL（Docker）
# 用法: bash scripts/mysql.sh up|down|status|wait

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT/deploy/mysql/compose.yml"
ENV_FILE="$ROOT/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "未找到 .env，请先: cp .env.example .env 并填写 MYSQL_*"
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
    echo "启动 jarvis-mysql..."
    compose up -d
    bash "$0" wait
    ;;
  down)
    echo "停止 jarvis-mysql（数据卷会保留）..."
    compose down
    ;;
  status)
    docker ps -a --filter name=jarvis-mysql --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
    ;;
  wait)
    echo "等待 MySQL 就绪..."
    for i in $(seq 1 60); do
      if docker exec jarvis-mysql mysqladmin ping -h 127.0.0.1 --silent >/dev/null 2>&1; then
        echo "jarvis-mysql 已就绪"
        exit 0
      fi
      sleep 2
    done
    echo "MySQL 启动超时，请查看: docker logs jarvis-mysql"
    docker logs --tail 40 jarvis-mysql || true
    exit 1
    ;;
  *)
    echo "用法: bash scripts/mysql.sh up|down|status|wait"
    exit 1
    ;;
esac
