import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from app.models import DistributedRateLimitBucket


def _utc_now() -> datetime:
    return datetime.now(UTC)


class PostgresRequestRateLimiter:
    """Reserve provider request slots across every application replica."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime] = _utc_now,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self._sleeper = sleeper

    async def acquire(
        self,
        *,
        bucket_key: str,
        minimum_interval_seconds: float,
    ) -> None:
        normalized_key = bucket_key.strip().lower()
        if not normalized_key or len(normalized_key) > 160:
            raise ValueError("Rate-limit bucket keys must contain 1 to 160 characters.")
        if minimum_interval_seconds <= 0:
            raise ValueError("minimum_interval_seconds must be positive.")

        requested_at = self._clock().astimezone(UTC)
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    insert(DistributedRateLimitBucket)
                    .values(
                        bucket_key=normalized_key,
                        next_permit_at=requested_at,
                    )
                    .on_conflict_do_nothing(index_elements=["bucket_key"])
                )
                bucket = await session.scalar(
                    select(DistributedRateLimitBucket)
                    .where(
                        DistributedRateLimitBucket.bucket_key == normalized_key
                    )
                    .with_for_update()
                )
                if bucket is None:
                    raise RuntimeError("Rate-limit bucket reservation failed.")
                permit_at = max(requested_at, bucket.next_permit_at)
                bucket.next_permit_at = permit_at + timedelta(
                    seconds=minimum_interval_seconds
                )

        wait_seconds = (permit_at - self._clock().astimezone(UTC)).total_seconds()
        if wait_seconds > 0:
            await self._sleeper(wait_seconds)


@asynccontextmanager
async def postgres_advisory_lease(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    lock_id: int,
) -> AsyncIterator[bool]:
    """Yield whether this replica owns one session-scoped PostgreSQL lease."""
    bind = session_factory.kw.get("bind")

    @asynccontextmanager
    async def hold(connection: AsyncConnection) -> AsyncIterator[bool]:
        acquired = bool(
            await connection.scalar(select(func.pg_try_advisory_lock(lock_id)))
        )
        try:
            yield acquired
        finally:
            if acquired:
                await connection.execute(select(func.pg_advisory_unlock(lock_id)))

    if isinstance(bind, AsyncConnection):
        async with hold(bind) as acquired:
            yield acquired
        return
    if not isinstance(bind, AsyncEngine):
        raise RuntimeError("Advisory leases require an async PostgreSQL bind.")

    async with bind.connect() as connection:
        autocommit_connection = await connection.execution_options(
            isolation_level="AUTOCOMMIT"
        )
        async with hold(autocommit_connection) as acquired:
            yield acquired
