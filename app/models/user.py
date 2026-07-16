from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import utc_now


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    email_verified: Mapped[datetime | None] = mapped_column(
        "emailVerified",
        DateTime(timezone=True),
        nullable=True,
    )
    customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    price_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    has_access: Mapped[bool] = mapped_column(Boolean, default=False)
    credits: Mapped[int] = mapped_column(Integer, default=0)
