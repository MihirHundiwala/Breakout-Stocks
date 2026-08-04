from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import func, select

from app.core.config import Settings, get_settings
from app.db.session import async_session_factory
from app.models import AnalysisSnapshot
from app.providers.upstox import UpstoxClient
from app.services.market_sessions import resolve_latest_available_nse_session
from app.services.distributed_rate_limit import PostgresRequestRateLimiter


async def resolve_watchlist_target_session(
    instrument_id: Annotated[int, Path(ge=1)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> date:
    if settings.application_mode == "snapshot":
        async with async_session_factory() as session:
            target = await session.scalar(
                select(func.max(AnalysisSnapshot.analysis_date)).where(
                    AnalysisSnapshot.instrument_id == instrument_id
                )
            )
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="ANALYSIS_SESSION_UNAVAILABLE",
            )
        return target

    if settings.upstox_access_token is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MARKET_DATA_NOT_CONFIGURED",
        )

    async with UpstoxClient(
        access_token=settings.upstox_access_token,
        timeout_seconds=settings.upstox_timeout_seconds,
        requests_per_second=settings.worker_upstox_requests_per_second,
        request_rate_limiter=PostgresRequestRateLimiter(
            async_session_factory
        ),
    ) as provider:
        try:
            return await resolve_latest_available_nse_session(
                provider,
                benchmark_instrument_key=settings.nifty_500_instrument_key,
                now=datetime.now(UTC),
            )
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MARKET_SESSION_UNAVAILABLE",
            ) from error
