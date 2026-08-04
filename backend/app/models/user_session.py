from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.models.app_user import AppUser


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        CheckConstraint(
            "token_digest ~ '^[0-9a-f]{64}$'",
            name="ck_user_sessions_token_digest_hex",
        ),
        CheckConstraint(
            "csrf_token_digest ~ '^[0-9a-f]{64}$'",
            name="ck_user_sessions_csrf_digest_hex",
        ),
        CheckConstraint(
            "expires_at > created_at",
            name="ck_user_sessions_expiry_after_creation",
        ),
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="ck_user_sessions_revoked_after_creation",
        ),
        UniqueConstraint(
            "token_digest",
            name="uq_user_sessions_token_digest",
        ),
        Index("ix_user_sessions_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("app_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    csrf_token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["AppUser"] = relationship(back_populates="sessions")
