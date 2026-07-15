from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class SiteStatus(StrEnum):
    initializing = "initializing"
    active = "active"
    paused = "paused"
    failed = "failed"


class CheckFrequency(StrEnum):
    six_hours = "six_hours"
    twelve_hours = "twelve_hours"
    daily = "daily"
    weekly = "weekly"


DEFAULT_TRACKED_CHANGE_TYPES = ["added", "removed", "updated"]


def default_tracked_change_types() -> list[str]:
    return DEFAULT_TRACKED_CHANGE_TYPES.copy()


class Site(TimestampMixin, Base):
    __tablename__ = "sites"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_user_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(255))
    root_url: Mapped[str] = mapped_column(Text)
    sitemap_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=SiteStatus.active.value)
    check_frequency: Mapped[str] = mapped_column(String(32), default=CheckFrequency.daily.value)
    tracked_change_types: Mapped[list[str]] = mapped_column(
        JSON,
        default=default_tracked_change_types,
    )
    baseline_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    baseline_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    baseline_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checking_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
