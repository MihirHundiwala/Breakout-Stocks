from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppUser, UserRole


async def get_user_by_username(
    session: AsyncSession,
    username: str,
) -> AppUser | None:
    return await session.scalar(
        select(AppUser).where(AppUser.username == username)
    )


async def get_admin_user_for_update(session: AsyncSession) -> AppUser | None:
    return await session.scalar(
        select(AppUser)
        .where(AppUser.role == UserRole.ADMIN)
        .with_for_update()
    )
