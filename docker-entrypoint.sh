#!/usr/bin/env bash
set -euo pipefail

service_type="${SERVICE_TYPE:-web}"

case "$service_type" in
  web)
    exec uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
    ;;
  worker)
    exec celery -A app.tasks.celery_app worker --loglevel="${LOG_LEVEL:-info}" --queues="${CELERY_QUEUE_NAME:-sitemap_monitor}" --hostname="sitemap-monitor-worker@%h"
    ;;
  beat)
    exec celery -A app.tasks.celery_app beat --loglevel="${LOG_LEVEL:-info}"
    ;;
  migrate)
    exec python -m alembic upgrade head
    ;;
  *)
    echo "Unknown SERVICE_TYPE: $service_type"
    echo "Supported values: web, worker, beat, migrate"
    exit 1
    ;;
esac
