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
    lastmod_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    last_seen_check_id: UUID | None
    removed_at: datetime | None


class SitemapUrlListRead(BaseModel):
    items: list[SitemapUrlRead]
    total: int
    limit: int
    offset: int


class UrlInsightsOverviewRead(BaseModel):
    total_urls: int
    with_lastmod: int
    without_lastmod: int


class UrlInsightsStructureNodeRead(BaseModel):
    path: str
    url_count: int
    children: list["UrlInsightsStructureNodeRead"]


class UrlInsightsUpdatesRead(BaseModel):
    modified_last_24h: int
    modified_last_7d: int
    modified_last_30d: int


class UrlInsightsRead(BaseModel):
    overview: UrlInsightsOverviewRead
    structure: UrlInsightsStructureNodeRead
    updates: UrlInsightsUpdatesRead
