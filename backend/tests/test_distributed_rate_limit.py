from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import async_session_factory
from app.services.distributed_rate_limit import (
    PostgresRequestRateLimiter,
    postgres_advisory_lease,
)


NOW = datetime(2026, 8, 1, 8, 30, tzinfo=UTC)


@pytest.mark.anyio
async def test_postgres_rate_limiter_reserves_shared_slots(
    db_session: AsyncSession,
) -> None:
    waits: list[float] = []

    async def record_wait(seconds: float) -> None:
        waits.append(seconds)

    factory = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    limiter = PostgresRequestRateLimiter(
        factory,
        clock=lambda: NOW,
        sleeper=record_wait,
    )

    await limiter.acquire(bucket_key="upstox:test", minimum_interval_seconds=1)
    await limiter.acquire(bucket_key="UPSTOX:TEST", minimum_interval_seconds=1)
    await limiter.acquire(bucket_key="telegram:test", minimum_interval_seconds=1)

    assert waits == [1.0]


@pytest.mark.anyio
async def test_postgres_advisory_lease_has_one_owner() -> None:
    async with postgres_advisory_lease(
        async_session_factory,
        lock_id=7_431_902_616,
    ) as first_owner:
        async with postgres_advisory_lease(
            async_session_factory,
            lock_id=7_431_902_616,
        ) as second_owner:
            assert first_owner is True
            assert second_owner is False
