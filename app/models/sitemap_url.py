from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class SitemapUrl(TimestampMixin, Base):
    __tablename__ = "sitemap_urls"
    __table_args__ = (
        UniqueConstraint("site_id", "url_hash", name="uq_sitemap_urls_site_id_url_hash"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    site_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    url_hash: Mapped[str] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(Text)
    lastmod: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lastmod_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_check_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
