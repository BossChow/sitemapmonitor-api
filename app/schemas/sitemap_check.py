from datetime import datetime
from uuid import UUID

from app.schemas.common import OrmModel


class SitemapCheckRead(OrmModel):
    id: UUID
    owner_user_id: str
    site_id: UUID
    status: str
    started_at: datetime
    finished_at: datetime | None
    url_count: int
    added_count: int
    removed_count: int
    updated_count: int
    error_message: str | None


class SitemapCheckChangeRead(OrmModel):
    id: UUID
    change_type: str
    url: str
    old_lastmod: str | None
    new_lastmod: str | None
    created_at: datetime


class SitemapCheckWithChangesRead(OrmModel):
    id: UUID
    site_id: UUID
    status: str
    started_at: datetime
    finished_at: datetime | None
    url_count: int
    added_count: int
    removed_count: int
    updated_count: int
    error_message: str | None
    change_count: int
    changes: list[SitemapCheckChangeRead]
