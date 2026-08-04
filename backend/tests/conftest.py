from collections.abc import AsyncIterator

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine
from app.models import (
    AdminSession,
    AppUser,
    AnalysisJob,
    AnalysisSnapshot,
    BenchmarkDailyCandle,
    Company,
    DailyCandle,
    DistributedRateLimitBucket,
    FundamentalPeriod,
    FundamentalSnapshot,
    Instrument,
    MarketBenchmark,
    ProviderInstrumentIdentity,
    TrackedInstrument,
    TelegramBotState,
    TelegramConnection,
    TelegramNotification,
    UserWatchlistItem,
    UserSession,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with engine.connect() as connection:
        transaction = await connection.begin()

        # Establish an empty test view without destroying committed local data.
        # The outer transaction restores these rows during teardown.
        await connection.execute(delete(UserSession))
        await connection.execute(delete(TelegramNotification))
        await connection.execute(delete(TelegramConnection))
        await connection.execute(delete(TelegramBotState))
        await connection.execute(delete(DistributedRateLimitBucket))
        await connection.execute(delete(AnalysisJob))
        await connection.execute(delete(UserWatchlistItem))
        await connection.execute(delete(TrackedInstrument))
        await connection.execute(delete(AnalysisSnapshot))
        await connection.execute(delete(BenchmarkDailyCandle))
        await connection.execute(delete(DailyCandle))
        await connection.execute(delete(FundamentalSnapshot))
        await connection.execute(delete(FundamentalPeriod))
        await connection.execute(delete(ProviderInstrumentIdentity))
        await connection.execute(delete(Instrument))
        await connection.execute(delete(MarketBenchmark))
        await connection.execute(delete(Company))
        await connection.execute(delete(AppUser))

        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        try:
            yield session
        finally:
            await session.close()
            if transaction.is_active:
                await transaction.rollback()
