#!/bin/bash
# Jarvis - 停止脚本（实现）
# 用法: bash scripts/stop.sh

BACKEND_PORT=1690
FRONTEND_PORT=5173
BACKEND_PID_FILE="/tmp/jarvis-backend.pid"
FRONTEND_PID_FILE="/tmp/jarvis-frontend.pid"

stop_port() {
  local port="$1"
  local name="$2"
  local pids
  pids=$(lsof -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | sort -u || true)
  if [ -z "$pids" ]; then
    echo "$name 未在运行 (端口 $port)"
    return
  fi
  echo "$pids" | xargs kill 2>/dev/null || true
  sleep 1
  local still
  still=$(lsof -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | sort -u || true)
  if [ -n "$still" ]; then
    echo "$still" | xargs kill -9 2>/dev/null || true
  fi
  echo "$name 已停止 (端口 $port, PID: $(echo $pids | tr '\n' ' '))"
}

stop_port "$FRONTEND_PORT" "前端"
stop_port "$BACKEND_PORT" "后端"

rm -f "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE" 2>/dev/null || true
echo "Jarvis 网页已停止（MySQL / Milvus 未动，全关请用 stop-all.sh）"
