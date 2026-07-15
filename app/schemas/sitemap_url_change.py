from datetime import datetime
from uuid import UUID

from app.schemas.common import OrmModel


class SitemapUrlChangeRead(OrmModel):
    id: UUID
    owner_user_id: str
    site_id: UUID
    check_id: UUID
    url_id: UUID | None
    change_type: str
    url: str
    old_lastmod: str | None
    new_lastmod: str | None
    created_at: datetime
