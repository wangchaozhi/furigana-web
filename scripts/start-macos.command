#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "未找到 Docker。请先安装并启动 Docker Desktop。"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker 服务未运行，请先启动 Docker Desktop。"
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "已从 .env.example 创建 .env。自动翻译需要在 .env 中填写 OPENAI_API_KEY。"
fi

echo "正在构建并启动 Furigana Studio..."
docker compose up --build -d

deadline=$((SECONDS + 300))
until curl -fsS http://localhost:3000 >/dev/null 2>&1 \
  && curl -fsS http://localhost:8000/health >/dev/null 2>&1; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    docker compose ps
    echo "服务未在 5 分钟内就绪，请运行 docker compose logs 查看日志。"
    exit 1
  fi
  sleep 2
done

echo "Furigana Studio 已启动：http://localhost:3000"
open http://localhost:3000
