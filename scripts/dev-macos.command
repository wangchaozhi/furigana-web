#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_DIR="$PROJECT_ROOT/api"
WEB_DIR="$PROJECT_ROOT/web"
VENV_DIR="$API_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"

if ! command -v python3 >/dev/null 2>&1; then
  echo "未找到 Python 3。请先安装 Python 3.12。"
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "未找到 npm。请先安装 Node.js 22。"
  exit 1
fi

find_available_port() {
  local port="$1"
  local last_port=$((port + 99))
  while [ "$port" -le "$last_port" ]; do
    if ! lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "$port"
      return 0
    fi
    port=$((port + 1))
  done
  echo "从端口 $1 开始连续 100 个端口均被占用。" >&2
  return 1
}

cd "$PROJECT_ROOT"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "已从 .env.example 创建 .env。"
fi
mkdir -p data

if [ ! -x "$PYTHON" ]; then
  echo "正在创建 Python 虚拟环境..."
  python3 -m venv "$VENV_DIR"
fi

echo "正在检查后端依赖..."
"$PYTHON" -m pip install -r "$API_DIR/requirements-dev.txt"

echo "正在检查前端依赖..."
(cd "$WEB_DIR" && npm install)

WEB_PORT="$(find_available_port 3000)"
API_PORT="$(find_available_port 8000)"
WEB_URL="http://localhost:$WEB_PORT"
API_URL="http://localhost:$API_PORT"

API_PID=""
WEB_PID=""
READY_PID=""
cleanup() {
  trap - INT TERM EXIT
  [ -n "$READY_PID" ] && kill "$READY_PID" 2>/dev/null || true
  [ -n "$API_PID" ] && kill "$API_PID" 2>/dev/null || true
  [ -n "$WEB_PID" ] && kill "$WEB_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "正在启动开发服务器（修改源码会自动更新）..."
echo "Web: $WEB_URL"
echo "API: $API_URL"
(cd "$API_DIR" && \
  DB_PATH="$PROJECT_ROOT/data/furigana.sqlite3" \
  CORS_ORIGINS="$WEB_URL" \
  "$PYTHON" -m uvicorn app.main:app --env-file "$PROJECT_ROOT/.env" --reload --port "$API_PORT") &
API_PID=$!

(cd "$WEB_DIR" && \
  NEXT_PUBLIC_API_BASE_URL="$API_URL" \
  npm run dev -- -p "$WEB_PORT") &
WEB_PID=$!

(
  for _ in {1..120}; do
    if curl -fsS "$WEB_URL" >/dev/null 2>&1; then
      echo "开发环境已启动：$WEB_URL"
      open "$WEB_URL"
      exit 0
    fi
    sleep 1
  done
  echo "页面尚未就绪，请检查上方日志。"
) &
READY_PID=$!

wait "$API_PID" "$WEB_PID"
