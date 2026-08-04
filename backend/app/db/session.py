from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.db.url import build_database_url


settings = get_settings()

database_url = build_database_url(settings)

engine: AsyncEngine = create_async_engine(
    database_url,
    pool_pre_ping=True,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout_seconds,
    connect_args={
        "connect_timeout": settings.database_connect_timeout_seconds,
        "options": (
            "-c statement_timeout="
            f"{settings.database_statement_timeout_seconds * 1000}"
        ),
    },
)

async_session_factory: async_sessionmaker[AsyncSession] = (
    async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
