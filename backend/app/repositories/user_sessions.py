from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import UserSession


async def get_active_user_session(
    session: AsyncSession,
    token_digest: str,
    occurred_at: datetime,
) -> UserSession | None:
    statement = (
        select(UserSession)
        .options(joinedload(UserSession.user))
        .join(UserSession.user)
        .where(
            UserSession.token_digest == token_digest,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > occurred_at,
            UserSession.user.has(is_active=True),
        )
    )
    return await session.scalar(statement)
