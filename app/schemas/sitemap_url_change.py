from datetime import datetime

from app.schemas.common import OrmModel


class SitemapUrlChangeRead(OrmModel):
    id: int
    owner_user_id: str
    site_id: int
    check_id: int
    url_id: int | None
    change_type: str
    url: str
    old_lastmod: str | None
    new_lastmod: str | None
    created_at: datetime

