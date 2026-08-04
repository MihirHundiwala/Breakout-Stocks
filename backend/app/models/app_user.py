from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    Identity,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.status import UserRole


if TYPE_CHECKING:
    from app.models.telegram_connection import TelegramConnection
    from app.models.user_session import UserSession
    from app.models.user_watchlist_item import UserWatchlistItem


class AppUser(Base):
    __tablename__ = "app_users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_app_users_username"),
        CheckConstraint(
            "username = btrim(username) AND username = lower(username) AND username <> ''",
            name="ck_app_users_username_normalized",
        ),
        CheckConstraint(
            "(role = 'ADMIN' AND password_hash IS NULL) OR "
            "(role = 'USER' AND password_hash IS NOT NULL "
            "AND password_hash LIKE '$argon2%')",
            name="ck_app_users_role_password_hash",
        ),
        CheckConstraint(
            "updated_at >= created_at",
            name="ck_app_users_updated_at",
        ),
        Index(
            "uq_app_users_single_admin",
            "role",
            unique=True,
            postgresql_where=text("role = 'ADMIN'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(
            UserRole,
            name="ck_app_users_role",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            length=16,
        ),
        nullable=False,
    )
    password_hash: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_active_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    watchlist_items: Mapped[list["UserWatchlistItem"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    telegram_connection: Mapped["TelegramConnection | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
