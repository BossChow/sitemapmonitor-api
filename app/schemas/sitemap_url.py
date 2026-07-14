from datetime import datetime

from app.schemas.common import TimestampedModel


class SitemapUrlRead(TimestampedModel):
    id: int
    site_id: int
    url_hash: str
    url: str
    lastmod: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    last_seen_check_id: int | None
    removed_at: datetime | None

