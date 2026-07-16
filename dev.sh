#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

export UV_CACHE_DIR="${UV_CACHE_DIR:-.uv-cache}"

command="${1:-api}"

case "$command" in
  api)
    uv run uvicorn app.main:app --reload --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}"
    ;;
  worker)
    uv run celery -A app.tasks.celery_app worker --loglevel="${LOG_LEVEL:-info}" --queues="${CELERY_QUEUE_NAME:-sitemap_monitor}" --hostname="sitemap-monitor-worker@%h"
    ;;
  beat)
    uv run celery -A app.tasks.celery_app beat --loglevel="${LOG_LEVEL:-info}"
    ;;
  migrate)
    uv run python -m alembic upgrade head
    ;;
  check)
    uv run python scripts/check_runtime.py
    ;;
  test)
    uv run ruff check .
    uv run pytest -q
    ;;
  sync)
    uv sync --extra dev
    ;;
  *)
    echo "Usage: ./dev.sh [api|worker|beat|migrate|check|test|sync]"
    exit 1
    ;;
esac
