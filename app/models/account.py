from uuid import UUID, uuid4

from sqlalchemy import BigInteger, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column("userId", Uuid(as_uuid=True))
    type: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(255))
    provider_account_id: Mapped[str] = mapped_column("providerAccountId", String(255))
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    id_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_type: Mapped[str | None] = mapped_column(Text, nullable=True)
