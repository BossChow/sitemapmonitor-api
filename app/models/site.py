from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class SiteStatus(StrEnum):
    active = "active"
    paused = "paused"


class CheckFrequency(StrEnum):
    six_hours = "six_hours"
    twelve_hours = "twelve_hours"
    daily = "daily"
    weekly = "weekly"


class Site(TimestampMixin, Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(255))
    root_url: Mapped[str] = mapped_column(Text)
    sitemap_url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default=SiteStatus.active.value)
    check_frequency: Mapped[str] = mapped_column(String(32), default=CheckFrequency.daily.value)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    checks = relationship("SitemapCheck", back_populates="site", cascade="all, delete-orphan")

