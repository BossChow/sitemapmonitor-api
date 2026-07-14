#!/usr/bin/env python3
from __future__ import annotations

import getpass
import secrets
import string
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import psycopg
from psycopg import sql

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT_NAME = "sitemap_monitor"
DEFAULT_HOST = "170.205.38.217"
DEFAULT_PORT = "5432"
DEFAULT_ADMIN_USER = "root"
REQUIRED_TABLES = {
    "sites",
    "sitemap_checks",
    "sitemap_urls",
    "sitemap_url_changes",
}


def question(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or (default or "")


def assert_valid_identifier(value: str, label: str) -> None:
    if not value:
        raise ValueError(f"{label} is required")
    if not value.replace("_", "a").isalnum() or not (value[0].isalpha() or value[0] == "_"):
        raise ValueError(
            f"{label} must start with a letter or underscore and contain only letters, "
            "numbers, and underscores"
        )


def generate_password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def admin_connect(
    host: str,
    port: str,
    admin_user: str,
    admin_password: str,
    dbname: str = "postgres",
):
    return psycopg.connect(
        host=host,
        port=int(port),
        user=admin_user,
        password=admin_password,
        dbname=dbname,
        connect_timeout=10,
        autocommit=True,
    )


def upsert_env_value(key: str, value: str) -> tuple[Path, str]:
    env_path = PROJECT_ROOT / ".env"
    line = f"{key}={value}"

    if not env_path.exists():
        env_path.write_text(f"{line}\n", encoding="utf-8")
        return env_path, "created"

    lines = env_path.read_text(encoding="utf-8").splitlines()
    prefix = f"{key}="
    for index, current_line in enumerate(lines):
        if current_line.strip().startswith(prefix):
            lines[index] = line
            env_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
            return env_path, "updated"

    lines.append(line)
    env_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return env_path, "appended"


def database_exists(conn, db_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        return cur.fetchone() is not None


def role_exists(conn, role_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role_name,))
        return cur.fetchone() is not None


def drop_database(conn, db_name: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = %s AND pid <> pg_backend_pid()
            """,
            (db_name,),
        )
        cur.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(db_name)))


def create_database(conn, db_name: str, app_user: str) -> None:
    with conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
        cur.execute(
            sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                sql.Identifier(db_name),
                sql.Identifier(app_user),
            )
        )


def upsert_role(conn, app_user: str, app_password: str) -> None:
    with conn.cursor() as cur:
        if role_exists(conn, app_user):
            print(f"   User '{app_user}' already exists, updating password...")
            cur.execute(
                sql.SQL("ALTER USER {} WITH PASSWORD {}").format(
                    sql.Identifier(app_user),
                    sql.Literal(app_password),
                )
            )
        else:
            cur.execute(
                sql.SQL("CREATE USER {} WITH PASSWORD {}").format(
                    sql.Identifier(app_user),
                    sql.Literal(app_password),
                )
            )


def grant_schema_privileges(
    host: str,
    port: str,
    admin_user: str,
    admin_password: str,
    db_name: str,
    app_user: str,
) -> None:
    with admin_connect(host, port, admin_user, admin_password, db_name) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(
                    sql.Identifier(app_user)
                )
            )
            cur.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {}").format(
                    sql.Identifier(app_user)
                )
            )
            cur.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {}"
                ).format(sql.Identifier(app_user))
            )
            cur.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {}").format(
                    sql.Identifier(app_user)
                )
            )
            cur.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {}"
                ).format(sql.Identifier(app_user))
            )


def build_database_url(host: str, port: str, db_name: str, app_user: str, app_password: str) -> str:
    return (
        f"postgresql+psycopg://{quote(app_user, safe='')}:{quote(app_password, safe='')}"
        f"@{quote(host, safe='')}:{port}/{quote(db_name, safe='')}"
    )


def test_database_url(database_url: str) -> None:
    with psycopg.connect(database_url.replace("postgresql+psycopg://", "postgresql://")) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user, current_database()")
            user, db_name = cur.fetchone()
            print("DATABASE_URL connection test successful")
            print(f"   Connected as: {user}")
            print(f"   Database: {db_name}")


def run_alembic_upgrade() -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        check=True,
    )


def list_project_tables(database_url: str) -> set[str]:
    with psycopg.connect(database_url.replace("postgresql+psycopg://", "postgresql://")) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
                """
            )
            return {row[0] for row in cur.fetchall()}


def main() -> None:
    print("Sitemap Monitor Database Setup Script")
    print("=" * 50)
    print()

    project_name = question("Project Name", DEFAULT_PROJECT_NAME)
    assert_valid_identifier(project_name, "Project name")

    default_db_name = f"{project_name}_db"
    default_app_user = f"{project_name}_user"

    print(f"\nProject: {project_name}")
    print(f"   Default database: {default_db_name}")
    print(f"   Default user: {default_app_user}")
    print()

    host = question("Database Host", DEFAULT_HOST)
    port = question("Database Port", DEFAULT_PORT)
    admin_user = question("Admin User", DEFAULT_ADMIN_USER)

    print(f"\nDatabase Server: {host}:{port}")
    print(f"   Admin User: {admin_user}\n")

    admin_password = getpass.getpass("Admin Password: ")
    if not admin_password:
        raise ValueError("Admin password is required")

    db_name = question("Database Name to create", default_db_name)
    app_user = question("Application Username", default_app_user)
    assert_valid_identifier(db_name, "Database name")
    assert_valid_identifier(app_user, "Application username")

    recommended_password = generate_password()
    app_password = question("Application Password", recommended_password)
    reset_existing = False

    print("\nConnecting to PostgreSQL server...")
    with admin_connect(host, port, admin_user, admin_password) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT now()")
        print("Connected successfully")

        if database_exists(conn, db_name):
            print(f"\nDatabase '{db_name}' already exists")
            print("WARNING: Dropping the database will DELETE ALL DATA!")
            confirm = question(f"Are you sure you want to delete '{db_name}'? Type yes/no", "no")
            if confirm.lower() == "yes":
                print("\nDropping existing database...")
                drop_database(conn, db_name)
                reset_existing = True
            else:
                print("Keeping existing database.")

        print(f"\nCreating or updating application user '{app_user}'...")
        upsert_role(conn, app_user, app_password)

        if not database_exists(conn, db_name):
            print(f"\nCreating database '{db_name}'...")
            create_database(conn, db_name, app_user)
            print(f"Database '{db_name}' created successfully")
        elif not reset_existing:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                        sql.Identifier(db_name),
                        sql.Identifier(app_user),
                    )
                )

    print(f"\nGranting schema privileges to '{app_user}'...")
    grant_schema_privileges(host, port, admin_user, admin_password, db_name, app_user)

    database_url = build_database_url(host, port, db_name, app_user, app_password)

    print("\nTesting generated DATABASE_URL...")
    print(f"   User: {app_user}")
    print(f"   Database: {db_name}")
    test_database_url(database_url)

    env_path, action = upsert_env_value("DATABASE_URL", database_url)
    print(f"\nDATABASE_URL {action} in {env_path.relative_to(PROJECT_ROOT)}")

    should_migrate = question("Run Alembic migrations now? yes/no", "yes")
    if should_migrate.lower() == "yes":
        print("\nRunning Alembic migrations...")
        run_alembic_upgrade()
        tables = list_project_tables(database_url)
        created_tables = sorted(REQUIRED_TABLES & tables)

        print("\nProject tables:")
        for table in created_tables:
            print(f"   - {table}")

        missing_tables = sorted(REQUIRED_TABLES - tables)
        if missing_tables:
            print(f"\nWarning: Missing expected tables: {', '.join(missing_tables)}")
        else:
            print("\nAll required tables are present")

    print("\n" + "=" * 50)
    print("Sitemap Monitor Database Setup Completed Successfully")
    print("\nNext steps:")
    print("   1. Start Redis if needed")
    print("   2. Start API: uvicorn app.main:app --reload")
    print("   3. Start worker: celery -A app.tasks.celery_app worker --loglevel=info")
    print("   4. Start beat: celery -A app.tasks.celery_app beat --loglevel=info")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSetup cancelled")
        raise SystemExit(1) from None
    except Exception as exc:
        print(f"\nSetup failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
