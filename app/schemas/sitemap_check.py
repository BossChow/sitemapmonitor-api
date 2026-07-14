from datetime import datetime

from app.schemas.common import OrmModel


class SitemapCheckRead(OrmModel):
    id: int
    owner_user_id: str
    site_id: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    url_count: int
    added_count: int
    removed_count: int
    updated_count: int
    error_message: str | None

