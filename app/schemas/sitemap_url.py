from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import TimestampedModel


class SitemapUrlRead(TimestampedModel):
    id: UUID
    site_id: UUID
    url_hash: str
    url: str
    lastmod: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    last_seen_check_id: UUID | None
    removed_at: datetime | None


class SitemapUrlListRead(BaseModel):
    items: list[SitemapUrlRead]
    total: int
    limit: int
    offset: int
