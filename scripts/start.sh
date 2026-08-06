#!/bin/bash
# Jarvis - 启动脚本（实现）
# 用法: bash scripts/start.sh

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_PORT=1690
FRONTEND_PORT=5173
LOG_DIR="/tmp"
BACKEND_LOG="$LOG_DIR/jarvis-backend.log"
FRONTEND_LOG="$LOG_DIR/jarvis-frontend.log"
BACKEND_PID_FILE="$LOG_DIR/jarvis-backend.pid"
FRONTEND_PID_FILE="$LOG_DIR/jarvis-frontend.pid"

kill_port() {
  local port="$1"
  local pids
  pids=$(lsof -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | sort -u || true)
  if [ -n "$pids" ]; then
    echo "端口 $port 已被占用，先关闭旧进程..."
    echo "$pids" | xargs kill 2>/dev/null || true
    sleep 1
    pids=$(lsof -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | sort -u || true)
    if [ -n "$pids" ]; then
      echo "$pids" | xargs kill -9 2>/dev/null || true
      sleep 1
    fi
  fi
}

if [ ! -f "$ROOT/.env" ]; then
  echo "未找到 .env，请先: cp .env.example .env 并填写 LLM_API_KEY"
  exit 1
fi

if [ ! -x "$ROOT/backend/.venv/bin/uvicorn" ]; then
  echo "后端虚拟环境未就绪，正在创建并安装依赖..."
  cd "$ROOT/backend"
  # mcp SDK 需要 Python >= 3.10；优先用 3.12
  PY=""
  for c in python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1; then
      ver=$("$c" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
      major=${ver%%.*}; minor=${ver#*.}
      if [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; }; then
        PY="$c"
        break
      fi
    fi
  done
  if [ -z "$PY" ]; then
    echo "需要 Python >= 3.10（推荐 3.12）以安装官方 mcp SDK"
    exit 1
  fi
  echo "使用 $PY ($($PY -V))"
  "$PY" -m venv .venv
  .venv/bin/pip install -U pip
  .venv/bin/pip install -r requirements.txt
fi

if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "前端依赖未安装，正在 npm install..."
  cd "$ROOT/frontend"
  npm install
fi

echo "启动 Jarvis MySQL 容器..."
bash "$ROOT/scripts/mysql.sh" up
echo "启动 Jarvis Milvus 容器..."
bash "$ROOT/scripts/milvus.sh" up

kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"

# 后台启动并写 PID 文件，便于 stop.sh 一键回收。
echo "启动 Jarvis 后端 (:$BACKEND_PORT)..."
cd "$ROOT/backend"
export PYTHONPATH="$ROOT/backend"
nohup "$ROOT/backend/.venv/bin/uvicorn" app.main:app \
  --host 127.0.0.1 --port "$BACKEND_PORT" \
  > "$BACKEND_LOG" 2>&1 &
echo $! > "$BACKEND_PID_FILE"
disown $! 2>/dev/null || true

echo "启动 Jarvis 前端 (:$FRONTEND_PORT)..."
cd "$ROOT/frontend"
nohup npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" \
  > "$FRONTEND_LOG" 2>&1 &
echo $! > "$FRONTEND_PID_FILE"
disown $! 2>/dev/null || true

BACKEND_OK=0
FRONTEND_OK=0
# 启动后做健康探测，给出更易理解的状态提示。
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -sf "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null 2>&1; then
    BACKEND_OK=1
    break
  fi
  sleep 1
done
if curl -sf "http://127.0.0.1:$FRONTEND_PORT/" >/dev/null 2>&1; then
  FRONTEND_OK=1
fi

echo ""
echo "  ================================"
if [ "$BACKEND_OK" -eq 1 ] && [ "$FRONTEND_OK" -eq 1 ]; then
  echo "  Jarvis 启动成功!"
elif [ "$BACKEND_OK" -eq 1 ]; then
  echo "  后端已启动，前端仍在加载或失败"
else
  echo "  启动异常，请查看日志"
fi
echo "  前端: http://127.0.0.1:$FRONTEND_PORT"
echo "  后端: http://127.0.0.1:$BACKEND_PORT"
echo "  文档: http://127.0.0.1:$BACKEND_PORT/docs"
echo "  后端日志: $BACKEND_LOG"
echo "  前端日志: $FRONTEND_LOG"
echo "  停止: bash stop.sh"
echo "  ================================"
echo ""

if [ "$BACKEND_OK" -eq 1 ]; then
  QUOTES=$(curl -s "http://127.0.0.1:$BACKEND_PORT/api/health" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('quotes',0))" 2>/dev/null || echo "0")
  echo "  行情: ${QUOTES} 只"
  LLM=$(curl -s "http://127.0.0.1:$BACKEND_PORT/api/health" 2>/dev/null | python3 -c "import sys,json; print('已配置' if json.load(sys.stdin).get('llmConfigured') else '未配置')" 2>/dev/null || echo "未知")
  echo "  LLM: $LLM"
  echo ""
fi

if [ "$BACKEND_OK" -ne 1 ]; then
  echo "后端失败，日志末尾："
  tail -n 30 "$BACKEND_LOG" 2>/dev/null || true
  exit 1
fi
