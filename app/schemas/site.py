from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, computed_field, field_validator

from app.models.site import CheckFrequency, SiteStatus
from app.models.sitemap_url_change import ChangeType
from app.schemas.common import TimestampedModel


def dedupe_change_types(values: list[ChangeType]) -> list[ChangeType]:
    return list(dict.fromkeys(values))


class SiteCreate(BaseModel):
    name: str | None = None
    root_url: HttpUrl
    sitemap_url: HttpUrl | None = None
    check_frequency: CheckFrequency
    tracked_change_types: list[ChangeType] = Field(min_length=1)

    @field_validator("tracked_change_types")
    @classmethod
    def validate_tracked_change_types(cls, values: list[ChangeType]) -> list[ChangeType]:
        return dedupe_change_types(values)


class SiteUpdate(BaseModel):
    name: str | None = None
    root_url: HttpUrl | None = None
    sitemap_url: HttpUrl | None = None
    status: SiteStatus | None = None
    check_frequency: CheckFrequency | None = None
    tracked_change_types: list[ChangeType] | None = Field(default=None, min_length=1)

    @field_validator("tracked_change_types")
    @classmethod
    def validate_tracked_change_types(
        cls,
        values: list[ChangeType] | None,
    ) -> list[ChangeType] | None:
        if values is None:
            return values
        return dedupe_change_types(values)


class SiteRead(TimestampedModel):
    id: UUID
    owner_user_id: str
    name: str
    root_url: str
    sitemap_url: str | None
    status: str
    check_frequency: str
    tracked_change_types: list[str]
    baseline_started_at: datetime | None
    baseline_completed_at: datetime | None
    baseline_error_message: str | None
    last_checked_at: datetime | None
    checking_started_at: datetime | None
    next_check_at: datetime | None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def error_message(self) -> str | None:
        return self.baseline_error_message
