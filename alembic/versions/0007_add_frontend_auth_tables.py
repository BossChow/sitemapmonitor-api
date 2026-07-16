"""add frontend auth tables

Revision ID: 0007_add_frontend_auth_tables
Revises: 0006_make_sitemap_url_optional
Create Date: 2026-07-15 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_add_frontend_auth_tables"
down_revision: str | None = "0006_make_sitemap_url_optional"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(255),
            image TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            "emailVerified" TIMESTAMPTZ,
            customer_id VARCHAR(255),
            price_id VARCHAR(255),
            has_access BOOLEAN DEFAULT FALSE,
            credits INTEGER DEFAULT 0 NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_customer_id ON users(customer_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            "userId" UUID NOT NULL,
            type VARCHAR(255) NOT NULL,
            provider VARCHAR(255) NOT NULL,
            "providerAccountId" VARCHAR(255) NOT NULL,
            refresh_token TEXT,
            access_token TEXT,
            expires_at BIGINT,
            id_token TEXT,
            scope TEXT,
            session_state TEXT,
            token_type TEXT
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS accounts_provider_providerAccountId_key
        ON accounts (provider, "providerAccountId")
        """
    )
    op.execute('CREATE INDEX IF NOT EXISTS accounts_userId_idx ON accounts ("userId")')

    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_users_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql'
        """
    )
    op.execute("DROP TRIGGER IF EXISTS update_users_updated_at ON users")
    op.execute(
        """
        CREATE TRIGGER update_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW
        EXECUTE FUNCTION update_users_updated_at_column()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS update_users_updated_at ON users")
    op.execute("DROP FUNCTION IF EXISTS update_users_updated_at_column")
    op.execute("DROP INDEX IF EXISTS accounts_userId_idx")
    op.execute("DROP INDEX IF EXISTS accounts_provider_providerAccountId_key")
    op.execute("DROP INDEX IF EXISTS idx_users_customer_id")
    op.execute("DROP INDEX IF EXISTS idx_users_email")
    op.execute("DROP TABLE IF EXISTS accounts")
    op.execute("DROP TABLE IF EXISTS users")
