import asyncio

from sqlalchemy import delete, select

from app.db.session import async_session_factory, engine
from app.fixtures.stocks import (
    FIXTURE_ALGORITHM_VERSION,
    FIXTURE_CANDLE_REVISION,
    STOCK_FIXTURES,
)
from app.models import (
    AnalysisJob,
    AnalysisSnapshot,
    Company,
    DailyCandle,
    FundamentalPeriod,
    FundamentalSnapshot,
    Instrument,
    ProviderInstrumentIdentity,
    TrackedInstrument,
    UserWatchlistItem,
)


async def main() -> int:
    symbols = tuple(item.trading_symbol for item in STOCK_FIXTURES)
    async with async_session_factory() as session:
        async with session.begin():
            instrument_ids = list(
                await session.scalars(
                    select(Instrument.id)
                    .where(
                        Instrument.exchange == "NSE",
                        Instrument.trading_symbol.in_(symbols),
                        select(AnalysisSnapshot.id)
                        .where(
                            AnalysisSnapshot.instrument_id == Instrument.id,
                            AnalysisSnapshot.source == "FIXTURE",
                            AnalysisSnapshot.algorithm_version
                            == FIXTURE_ALGORITHM_VERSION,
                            AnalysisSnapshot.candle_revision
                            == FIXTURE_CANDLE_REVISION,
                        )
                        .exists(),
                    )
                    .with_for_update(of=Instrument)
                )
            )
            if not instrument_ids:
                print("FIXTURE_PURGE_OK instruments=0 companies=0")
                return 0

            company_ids = list(
                await session.scalars(
                    select(Instrument.company_id).where(Instrument.id.in_(instrument_ids))
                )
            )
            tracking_ids = list(
                await session.scalars(
                    select(TrackedInstrument.id).where(
                        TrackedInstrument.instrument_id.in_(instrument_ids)
                    )
                )
            )
            await session.execute(
                delete(UserWatchlistItem).where(
                    UserWatchlistItem.instrument_id.in_(instrument_ids)
                )
            )
            if tracking_ids:
                await session.execute(
                    delete(AnalysisJob).where(
                        AnalysisJob.tracked_instrument_id.in_(tracking_ids)
                    )
                )
                await session.execute(
                    delete(TrackedInstrument).where(TrackedInstrument.id.in_(tracking_ids))
                )
            for model in (
                AnalysisSnapshot,
                DailyCandle,
                FundamentalSnapshot,
                ProviderInstrumentIdentity,
            ):
                await session.execute(
                    delete(model).where(model.instrument_id.in_(instrument_ids))
                )
            await session.execute(
                delete(FundamentalPeriod).where(
                    FundamentalPeriod.company_id.in_(company_ids)
                )
            )
            await session.execute(
                delete(Instrument).where(Instrument.id.in_(instrument_ids))
            )
            await session.execute(
                delete(Company).where(
                    Company.id.in_(company_ids),
                    ~select(Instrument.id)
                    .where(Instrument.company_id == Company.id)
                    .exists(),
                )
            )
        print(
            "FIXTURE_PURGE_OK "
            f"instruments={len(instrument_ids)} companies={len(company_ids)}"
        )
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
