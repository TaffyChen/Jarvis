#!/bin/bash
# 用法:
#   bash scripts/deploy.sh build          只打应用镜像（不启动）
#   bash scripts/deploy.sh save [文件]    把镜像导出成 tar 包
#   bash scripts/deploy.sh up             用已有/现编镜像启动应用+MySQL
#   bash scripts/deploy.sh down           停止
#   bash scripts/deploy.sh logs           看日志
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"
IMAGE="${JARVIS_IMAGE:-jarvis:local}"
COMPOSE=(-f "$ROOT/deploy/compose.yml")

if [ ! -f "$ENV_FILE" ]; then
  echo "未找到 .env，请先: cp .env.example .env"
  exit 1
fi

if grep -qE '^VECTOR_BACKEND=milvus' "$ENV_FILE"; then
  COMPOSE+=(-f "$ROOT/deploy/compose.milvus.yml")
fi

compose() {
  docker compose --env-file "$ENV_FILE" "${COMPOSE[@]}" "$@"
}

cmd="${1:-}"
case "$cmd" in
  build)
    echo "构建镜像 $IMAGE （不启动容器）..."
    docker build -f "$ROOT/deploy/Dockerfile" -t "$IMAGE" "$ROOT"
    echo "完成。本机镜像名: $IMAGE"
    echo "导出离线包: bash scripts/deploy.sh save"
    ;;
  save)
    stamp=$(date +%Y%m%d-%H%M%S)
    git_sha=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || true)
    if [ -n "$git_sha" ]; then
      default_name="jarvis-app-${stamp}-${git_sha}.tar"
    else
      default_name="jarvis-app-${stamp}.tar"
    fi
    out="${2:-$ROOT/deploy/dist/$default_name}"
    mkdir -p "$(dirname "$out")"
    echo "导出 $IMAGE -> $out"
    docker save "$IMAGE" -o "$out"
    ln -sfn "$(basename "$out")" "$ROOT/deploy/dist/jarvis-app-latest.tar"
    ls -lh "$out"
    echo "拷到服务器后: docker load -i $(basename "$out")"
    ;;
  up)
    echo "启动编排（不是解压 tar 自带配置）："
    echo "  镜像: $IMAGE"
    echo "  编排: ${COMPOSE[*]}"
    echo "  环境: $ENV_FILE"
    compose up -d
    port=$(grep -E '^JARVIS_PORT=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    echo "已启动。浏览器: http://127.0.0.1:${port:-1690}"
    ;;
  up-build)
    compose up -d --build
    echo "已重新构建并启动。"
    ;;
  down)
    compose down
    ;;
  logs)
    compose logs -f --tail=80
    ;;
  *)
    echo "用法: bash scripts/deploy.sh build|save|up|up-build|down|logs"
    exit 1
    ;;
esac
