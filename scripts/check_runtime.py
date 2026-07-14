#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import redis
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

REQUIRED_TABLES = {
    "sites",
    "sitemap_checks",
    "sitemap_urls",
    "sitemap_url_changes",
}


def mask_url(url: str) -> str:
    parts = urlsplit(url)
    if "@" not in parts.netloc:
        return url
    credentials, host = parts.netloc.rsplit("@", 1)
    user = credentials.split(":", 1)[0]
    return urlunsplit((parts.scheme, f"{user}:***@{host}", parts.path, parts.query, parts.fragment))


def check_postgres(database_url: str) -> None:
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as conn:
        current = conn.execute(text("SELECT current_user, current_database()")).one()
        rows = conn.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
                """
            )
        )
        tables = {row[0] for row in rows}

    print("Postgres: ok")
    print(f"   URL: {mask_url(database_url)}")
    print(f"   User: {current[0]}")
    print(f"   Database: {current[1]}")

    missing = sorted(REQUIRED_TABLES - tables)
    if missing:
        raise RuntimeError(f"Missing required tables: {', '.join(missing)}")
    print("   Tables: ok")


def check_redis(redis_url: str) -> None:
    client = redis.Redis.from_url(redis_url)
    if not client.ping():
        raise RuntimeError("Redis ping failed")
    print("Redis: ok")
    print(f"   URL: {redis_url}")


def main() -> None:
    from app.core.config import settings

    check_postgres(settings.database_url)
    check_redis(settings.redis_url)


if __name__ == "__main__":
    main()
