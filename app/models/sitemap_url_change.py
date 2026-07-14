from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import utc_now


class ChangeType(StrEnum):
    added = "added"
    removed = "removed"
    updated = "updated"


class SitemapUrlChange(Base):
    __tablename__ = "sitemap_url_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(String(128), index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"))
    check_id: Mapped[int] = mapped_column(ForeignKey("sitemap_checks.id", ondelete="CASCADE"))
    url_id: Mapped[int | None] = mapped_column(ForeignKey("sitemap_urls.id", ondelete="SET NULL"))
    change_type: Mapped[str] = mapped_column(String(32))
    url: Mapped[str] = mapped_column(Text)
    old_lastmod: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_lastmod: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

