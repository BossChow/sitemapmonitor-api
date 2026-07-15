# Sitemap Monitor

Backend service for monitoring sitemap changes.

## Run locally

```bash
./dev.sh sync
./dev.sh migrate
./dev.sh api
./dev.sh worker
./dev.sh beat
```

## Docker

```bash
docker build -t ghcr.io/bosschow/sitemap-monitor-api:latest .
docker compose up -d
```

The API is exposed on host port `5010`:

```text
http://your-vps-ip:5010/docs
```

The compose file expects the shared Docker network to exist:

```bash
docker network create infra
```

## Environment

```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/sitemap_monitor
REDIS_URL=redis://localhost:6379/0
CELERY_QUEUE_NAME=sitemap_monitor
```

## Shared PostgreSQL setup

To create a dedicated database and user on a shared PostgreSQL server:

```bash
bash scripts/setup_database.sh
```

The script writes `DATABASE_URL` to `.env` and can run Alembic migrations after the database is ready.

## Development commands

```bash
./dev.sh api      # Start FastAPI at http://127.0.0.1:8000
./dev.sh worker   # Start Celery worker
./dev.sh beat     # Start Celery Beat scheduler
./dev.sh migrate  # Run Alembic migrations
./dev.sh check    # Check Postgres and Redis connectivity
./dev.sh test     # Run lint and tests
./dev.sh sync     # Install dependencies
```

## Frontend integration

See [docs/frontend-api.md](docs/frontend-api.md) for endpoint order, required headers, and example frontend calls.
