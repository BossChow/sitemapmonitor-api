from datetime import datetime

from pydantic import BaseModel, HttpUrl

from app.models.site import CheckFrequency, SiteStatus
from app.schemas.common import TimestampedModel


class SiteCreate(BaseModel):
    name: str
    root_url: HttpUrl
    sitemap_url: HttpUrl
    check_frequency: CheckFrequency = CheckFrequency.daily


class SiteUpdate(BaseModel):
    name: str | None = None
    root_url: HttpUrl | None = None
    sitemap_url: HttpUrl | None = None
    status: SiteStatus | None = None
    check_frequency: CheckFrequency | None = None


class SiteRead(TimestampedModel):
    id: int
    owner_user_id: str
    name: str
    root_url: str
    sitemap_url: str
    status: str
    check_frequency: str
    last_checked_at: datetime | None
    next_check_at: datetime | None

