from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.models.app_user import AppUser


class TelegramConnection(Base):
    __tablename__ = "telegram_connections"
    __table_args__ = (
        CheckConstraint(
            "telegram_username IS NULL OR "
            "(telegram_username = lower(btrim(telegram_username)) "
            "AND telegram_username <> '')",
            name="ck_telegram_connections_username",
        ),
        CheckConstraint(
            "link_token_digest IS NULL OR "
            "link_token_digest ~ '^[0-9a-f]{64}$'",
            name="ck_telegram_connections_token_digest",
        ),
        CheckConstraint(
            "(telegram_chat_id IS NULL AND connected_at IS NULL "
            "AND link_token_digest IS NOT NULL AND link_expires_at IS NOT NULL) "
            "OR (telegram_chat_id IS NOT NULL AND connected_at IS NOT NULL "
            "AND link_token_digest IS NULL AND link_expires_at IS NULL)",
            name="ck_telegram_connections_state",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_users.id", ondelete="CASCADE"), primary_key=True
    )
    telegram_chat_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    telegram_username: Mapped[str | None] = mapped_column(String(32))
    link_token_digest: Mapped[str | None] = mapped_column(String(64), unique=True)
    link_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped["AppUser"] = relationship(back_populates="telegram_connection")


class TelegramBotState(Base):
    __tablename__ = "telegram_bot_state"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_telegram_bot_state_singleton"),
        CheckConstraint("next_update_id >= 0", name="ck_telegram_bot_state_update_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    next_update_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
