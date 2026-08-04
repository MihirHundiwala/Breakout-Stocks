from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.db.session import async_session_factory
from app.providers.upstox import UpstoxClient
from app.services.distributed_rate_limit import PostgresRequestRateLimiter


async def get_upstox_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[UpstoxClient]:
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
        yield provider
