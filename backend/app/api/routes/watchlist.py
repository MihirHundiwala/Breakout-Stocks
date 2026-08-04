from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    require_csrf,
    require_user_csrf,
    require_user_session,
)
from app.api.dependencies.providers import get_upstox_provider
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.models import BenchmarkDailyCandle, MarketBenchmark, UserRole, UserSession
from app.domain.market_math import percentage_change
from app.providers.contracts import InstrumentCandidate
from app.providers.errors import ProviderError
from app.providers.upstox import UpstoxClient
from app.schemas.watchlist import (
    AddedWatchlistItemResponse,
    BatchAddWatchlistRequest,
    BatchAddWatchlistResponse,
    InstrumentCandidateResponse,
    InstrumentSearchResponse,
    RefreshWatchlistResponse,
    RemoveWatchlistItemResponse,
    WatchlistItemResponse,
    WatchlistResponse,
)
from app.services.nightly_scan import (
    resolve_latest_known_session,
    schedule_active_watchlist,
    schedule_fundamental_refresh,
)
from app.services.watchlist import (
    InstrumentIdentityConflictError,
    InstrumentNotFoundError,
    WatchlistLimitExceededError,
    WatchlistMembershipNotFoundError,
    WatchlistUserNotFoundError,
    add_watchlist_memberships,
    ensure_upstox_instrument,
    get_watchlist,
    remove_watchlist_membership,
    purge_instrument_for_admin,
)


router = APIRouter(tags=["watchlist"])


def _provider_failure(error: ProviderError) -> HTTPException:
    if error.code == "UPSTOX_AUTH_FAILED":
        detail = "MARKET_DATA_AUTH_FAILED"
    elif error.code == "UPSTOX_RATE_LIMITED":
        detail = "MARKET_DATA_RATE_LIMITED"
    else:
        detail = "MARKET_DATA_UNAVAILABLE"
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=detail,
    )


def _watchlist_limit(user_session: UserSession, settings: Settings) -> int | None:
    if user_session.user.role == UserRole.ADMIN:
        return None
    return settings.normal_user_watchlist_limit


def _remaining_slots(limit: int | None, active_count: int) -> int | None:
    if limit is None:
        return None
    return max(limit - active_count, 0)


@router.get(
    "/watchlist/instruments",
    response_model=WatchlistResponse,
    summary="List the signed-in user's active watchlist",
)
async def list_watchlist(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user_session: Annotated[UserSession, Depends(require_user_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WatchlistResponse:
    records = await get_watchlist(session, user_session.user_id)
    limit = _watchlist_limit(user_session, settings)
    items = [
        WatchlistItemResponse(
            instrument_id=record.instrument.id,
            company_name=record.company.name,
            exchange=record.instrument.exchange,
            trading_symbol=record.instrument.trading_symbol,
            market_data_state=record.tracked_instrument.operational_state,
            target_session=record.tracked_instrument.target_session,
            added_at=(
                record.membership.reactivated_at
                or record.membership.created_at
            ),
            baseline_session=record.membership.baseline_session,
            baseline_close_price=record.membership.baseline_close_price,
            latest_close_price=(
                record.latest_analysis.close_price
                if record.latest_analysis is not None
                else None
            ),
            movement_since_added_percent=(
                percentage_change(
                    record.latest_analysis.close_price,
                    record.membership.baseline_close_price,
                )
                if record.latest_analysis is not None
                and record.membership.baseline_close_price is not None
                and record.latest_analysis.analysis_date
                >= record.membership.baseline_session
                else None
            ),
        )
        for record in records
    ]
    return WatchlistResponse(
        items=items,
        count=len(items),
        watchlist_limit=limit,
        remaining_slots=_remaining_slots(limit, len(items)),
    )


@router.get(
    "/watchlist/instruments/search",
    response_model=InstrumentSearchResponse,
    summary="Search Upstox NSE equity instruments",
)
async def search_instruments(
    query: Annotated[
        str,
        Query(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9 ]+$"),
    ],
    _user_session: Annotated[UserSession, Depends(require_user_session)],
    provider: Annotated[UpstoxClient, Depends(get_upstox_provider)],
) -> InstrumentSearchResponse:
    try:
        candidates = await provider.search_nse_equities(query=query, limit=20)
    except ProviderError as error:
        raise _provider_failure(error) from error
    items = [
        InstrumentCandidateResponse(
            company_name=item.company_name,
            exchange=item.exchange,
            trading_symbol=item.trading_symbol,
            isin=item.isin,
        )
        for item in candidates
    ]
    return InstrumentSearchResponse(items=items, count=len(items))


async def _resolve_candidates(
    provider: UpstoxClient,
    isins: list[str],
) -> list[InstrumentCandidate]:
    candidates: list[InstrumentCandidate] = []
    for isin in dict.fromkeys(isins):
        matches = await provider.search_nse_equities(query=isin, limit=20)
        candidate = next((item for item in matches if item.isin == isin), None)
        if candidate is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="UPSTOX_INSTRUMENT_NOT_FOUND",
            )
        candidates.append(candidate)
    return candidates


@router.post(
    "/watchlist/instruments",
    response_model=BatchAddWatchlistResponse,
    summary="Add one or more companies to the signed-in user's watchlist",
)
async def add_instruments(
    request: BatchAddWatchlistRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user_session: Annotated[UserSession, Depends(require_user_csrf)],
    provider: Annotated[UpstoxClient, Depends(get_upstox_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BatchAddWatchlistResponse:
    try:
        candidates = await _resolve_candidates(provider, request.isins)
        target_session = await resolve_latest_known_session(
            session,
            provider,
            benchmark_instrument_key=settings.nifty_500_instrument_key,
            now=datetime.now(UTC),
        )
    except ProviderError as error:
        raise _provider_failure(error) from error

    try:
        instruments = [
            await ensure_upstox_instrument(session, candidate)
            for candidate in candidates
        ]
        result = await add_watchlist_memberships(
            session,
            user_id=user_session.user_id,
            instrument_ids=[instrument.id for instrument in instruments],
            target_session=target_session,
            normal_user_limit=settings.normal_user_watchlist_limit,
            telegram_notifications_enabled=(
                settings.telegram_notifications_enabled
            ),
        )
    except InstrumentIdentityConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="INSTRUMENT_IDENTITY_UNRESOLVED",
        ) from error
    except InstrumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="INSTRUMENT_NOT_FOUND",
        ) from error
    except WatchlistLimitExceededError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "WATCHLIST_LIMIT_EXCEEDED",
                "limit": error.limit,
                "active_count": error.active_count,
                "requested_count": error.requested_count,
            },
        ) from error
    except WatchlistUserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="AUTHENTICATION_REQUIRED",
        ) from error

    return BatchAddWatchlistResponse(
        items=[
            AddedWatchlistItemResponse(
                instrument_id=item.membership.instrument_id,
                membership_created=item.membership_created,
                membership_reactivated=item.membership_reactivated,
                already_in_watchlist=(
                    not item.membership_created
                    and not item.membership_reactivated
                ),
                shared_analysis_started=(
                    item.tracking.created or item.tracking.reactivated
                ),
            )
            for item in result.items
        ],
        active_count=result.active_count,
        watchlist_limit=result.watchlist_limit,
        remaining_slots=_remaining_slots(
            result.watchlist_limit,
            result.active_count,
        ),
    )


@router.delete(
    "/watchlist/instruments/{instrument_id}",
    response_model=RemoveWatchlistItemResponse,
    summary="Remove a company from the signed-in user's watchlist",
)
async def remove_instrument(
    instrument_id: Annotated[int, Path(ge=1)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user_session: Annotated[UserSession, Depends(require_user_csrf)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RemoveWatchlistItemResponse:
    try:
        if user_session.user.role == UserRole.ADMIN:
            result = await purge_instrument_for_admin(
                session,
                user_id=user_session.user_id,
                instrument_id=instrument_id,
            )
        else:
            result = await remove_watchlist_membership(
                session,
                user_id=user_session.user_id,
                instrument_id=instrument_id,
                normal_user_limit=settings.normal_user_watchlist_limit,
            )
    except InstrumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WATCHLIST_ITEM_NOT_FOUND",
        ) from error
    except WatchlistMembershipNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WATCHLIST_ITEM_NOT_FOUND",
        ) from error
    except WatchlistUserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="AUTHENTICATION_REQUIRED",
        ) from error

    return RemoveWatchlistItemResponse(
        instrument_id=instrument_id,
        removed=True,
        active_count=result.active_count,
        watchlist_limit=(
            None
            if user_session.user.role == UserRole.ADMIN
            else result.watchlist_limit
        ),
        remaining_slots=_remaining_slots(
            (
                None
                if user_session.user.role == UserRole.ADMIN
                else result.watchlist_limit
            ),
            result.active_count,
        ),
    )


@router.post(
    "/admin/watchlist/instruments/refresh",
    response_model=RefreshWatchlistResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Fetch technical market data for all tracked companies",
)
async def refresh_watchlist(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _admin_session: Annotated[UserSession, Depends(require_csrf)],
    provider: Annotated[UpstoxClient, Depends(get_upstox_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RefreshWatchlistResponse:
    occurred_at = datetime.now(UTC)
    try:
        target_session = await resolve_latest_known_session(
            session,
            provider,
            benchmark_instrument_key=settings.nifty_500_instrument_key,
            now=occurred_at,
        )
    except ProviderError as error:
        raise _provider_failure(error) from error
    result = await schedule_active_watchlist(
        session,
        target_session=target_session,
        force_reanalysis=True,
        reuse_stored_market_data=False,
        occurred_at=occurred_at,
    )
    return RefreshWatchlistResponse(
        target_session=result.target_session,
        scheduled_count=result.enqueued_count + result.retargeted_count,
        already_updating_count=result.skipped_active_count,
        already_current_count=result.skipped_completed_count,
        terminal_data_failure_count=result.skipped_terminal_count,
    )


@router.post(
    "/admin/watchlist/instruments/rerun-algorithm",
    response_model=RefreshWatchlistResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-run the algorithm using stored market data",
)
async def rerun_watchlist_algorithm(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _admin_session: Annotated[UserSession, Depends(require_csrf)],
) -> RefreshWatchlistResponse:
    occurred_at = datetime.now(UTC)
    target_session = await session.scalar(
        select(func.max(BenchmarkDailyCandle.trading_date))
        .join(MarketBenchmark)
        .where(MarketBenchmark.code == "NIFTY_500")
    )
    await session.rollback()
    if target_session is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MARKET_DATA_NOT_READY",
        )
    result = await schedule_active_watchlist(
        session,
        target_session=target_session,
        force_reanalysis=True,
        reuse_stored_market_data=True,
        occurred_at=occurred_at,
    )
    return RefreshWatchlistResponse(
        target_session=result.target_session,
        scheduled_count=result.enqueued_count + result.retargeted_count,
        already_updating_count=result.skipped_active_count,
        already_current_count=result.skipped_completed_count,
        terminal_data_failure_count=result.skipped_terminal_count,
    )


@router.post(
    "/admin/watchlist/instruments/refresh-fundamentals",
    response_model=RefreshWatchlistResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Fetch fundamental data for all tracked companies",
)
async def refresh_watchlist_fundamentals(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _admin_session: Annotated[UserSession, Depends(require_csrf)],
) -> RefreshWatchlistResponse:
    occurred_at = datetime.now(UTC)
    target_session = await session.scalar(
        select(func.max(BenchmarkDailyCandle.trading_date))
        .join(MarketBenchmark)
        .where(MarketBenchmark.code == "NIFTY_500")
    )
    await session.rollback()
    if target_session is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MARKET_DATA_NOT_READY",
        )
    result = await schedule_fundamental_refresh(
        session,
        target_session=target_session,
        occurred_at=occurred_at,
    )
    return RefreshWatchlistResponse(
        target_session=result.target_session,
        scheduled_count=result.enqueued_count + result.retargeted_count,
        already_updating_count=result.skipped_active_count,
        already_current_count=result.skipped_completed_count,
        terminal_data_failure_count=result.skipped_terminal_count,
    )
