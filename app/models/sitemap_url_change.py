from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import utc_now


class ChangeType(StrEnum):
    added = "added"
    removed = "removed"
    updated = "updated"


class SitemapUrlChange(Base):
    __tablename__ = "sitemap_url_changes"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_user_id: Mapped[str] = mapped_column(String(128), index=True)
    site_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    check_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    url_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    change_type: Mapped[str] = mapped_column(String(32))
    url: Mapped[str] = mapped_column(Text)
    old_lastmod: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_lastmod: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
