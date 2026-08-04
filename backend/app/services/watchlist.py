from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalysisJob,
    AnalysisJobStatus,
    AnalysisJobType,
    AppUser,
    Company,
    Instrument,
    ProviderInstrumentIdentity,
    TrackedInstrument,
    TrackingOperationalState,
    UserRole,
    UserWatchlistItem,
)
from app.repositories.watchlist import (
    WatchlistRecord,
    count_active_followers_for_instrument,
    count_active_memberships_for_user,
    get_membership_for_update,
    get_user_for_update,
    get_instrument_for_update,
    get_active_identity_with_instrument_for_update,
    get_active_fundamental_job_for_update,
    get_instrument_by_symbol_for_update,
    get_latest_technical_job_for_update,
    get_close_for_session,
    get_tracking_for_update,
    has_fundamental_snapshot,
    list_active_jobs_for_update,
    list_watchlist_records,
)
from app.providers.contracts import InstrumentCandidate
from app.services.setup_notifications import (
    enqueue_existing_watchlist_setup_notification,
)


class WatchlistServiceError(Exception):
    """Base class for expected watchlist command failures."""


class InstrumentNotFoundError(WatchlistServiceError):
    def __init__(self, instrument_id: int) -> None:
        super().__init__(f"Instrument {instrument_id} was not found.")


class TrackedInstrumentNotFoundError(WatchlistServiceError):
    def __init__(self, instrument_id: int) -> None:
        super().__init__(
            f"Instrument {instrument_id} is not in the watchlist."
        )


class InstrumentIdentityConflictError(WatchlistServiceError):
    pass


class WatchlistUserNotFoundError(WatchlistServiceError):
    pass


class WatchlistMembershipNotFoundError(WatchlistServiceError):
    def __init__(self, instrument_id: int) -> None:
        super().__init__(
            f"Instrument {instrument_id} is not in this user's watchlist."
        )


class WatchlistLimitExceededError(WatchlistServiceError):
    def __init__(self, *, limit: int, active_count: int, requested_count: int) -> None:
        self.limit = limit
        self.active_count = active_count
        self.requested_count = requested_count
        super().__init__(
            f"Adding {requested_count} instruments would exceed the "
            f"watchlist limit of {limit}."
        )


def _provider_identity_lock_key(provider: str, isin: str) -> int:
    """Map one provider identity to PostgreSQL's signed 64-bit lock space."""
    digest = sha256(f"{provider}:{isin}".encode("utf-8")).digest()
    unsigned = int.from_bytes(digest[:8], byteorder="big", signed=False)
    return unsigned if unsigned < 2**63 else unsigned - 2**64


@dataclass(frozen=True, slots=True)
class TrackInstrumentResult:
    tracked_instrument: TrackedInstrument
    analysis_job: AnalysisJob | None
    created: bool
    reactivated: bool


@dataclass(frozen=True, slots=True)
class DeactivateInstrumentResult:
    tracked_instrument: TrackedInstrument
    cancelled_job_count: int
    already_inactive: bool


@dataclass(frozen=True, slots=True)
class AddMembershipResult:
    membership: UserWatchlistItem
    tracking: TrackInstrumentResult
    membership_created: bool
    membership_reactivated: bool


@dataclass(frozen=True, slots=True)
class AddMembershipsResult:
    user: AppUser
    items: list[AddMembershipResult]
    active_count: int
    watchlist_limit: int | None


@dataclass(frozen=True, slots=True)
class RemoveMembershipResult:
    membership: UserWatchlistItem
    tracked_instrument: TrackedInstrument
    active_count: int
    watchlist_limit: int | None
    remaining_follower_count: int
    shared_tracking_stopped: bool
    cancelled_job_count: int


@dataclass(frozen=True, slots=True)
class PurgeInstrumentResult:
    instrument_id: int
    active_count: int
    company_removed: bool


async def ensure_upstox_instrument(
    session: AsyncSession,
    candidate: InstrumentCandidate,
    *,
    fetched_at: datetime | None = None,
) -> Instrument:
    event_time = _event_time(fetched_at)
    async with session.begin():
        await session.scalar(
            select(
                func.pg_advisory_xact_lock(
                    _provider_identity_lock_key("UPSTOX", candidate.isin)
                )
            )
        )
        matched = await get_active_identity_with_instrument_for_update(
            session,
            provider="UPSTOX",
            instrument_key=candidate.instrument_key,
            isin=candidate.isin,
        )
        if matched is not None:
            identity, instrument, company = matched
            if identity.isin != candidate.isin:
                raise InstrumentIdentityConflictError(
                    "The active provider identity does not match the selected ISIN."
                )
            company.name = candidate.company_name
            instrument.trading_symbol = candidate.trading_symbol
            identity.instrument_key = candidate.instrument_key
            identity.source_fetched_at = event_time
            await session.flush()
            return instrument

        existing = await get_instrument_by_symbol_for_update(
            session,
            exchange=candidate.exchange,
            trading_symbol=candidate.trading_symbol,
        )
        if existing is None:
            company = Company(name=candidate.company_name)
            instrument = Instrument(
                company=company,
                exchange=candidate.exchange,
                trading_symbol=candidate.trading_symbol,
            )
            session.add(instrument)
            await session.flush()
        else:
            instrument, company = existing
            company.name = candidate.company_name

        session.add(
            ProviderInstrumentIdentity(
                instrument_id=instrument.id,
                provider="UPSTOX",
                instrument_key=candidate.instrument_key,
                isin=candidate.isin,
                effective_from=event_time.date(),
                source_fetched_at=event_time,
            )
        )
        await session.flush()
        return instrument


def _event_time(value: datetime | None) -> datetime:
    event_time = value or datetime.now(UTC)
    if event_time.tzinfo is None or event_time.utcoffset() is None:
        raise ValueError("Event timestamps must be timezone-aware.")
    return event_time.astimezone(UTC)


def _new_pending_job(
    tracked_instrument: TrackedInstrument,
    target_session: date,
    created_at: datetime,
    *,
    job_type: AnalysisJobType,
) -> AnalysisJob:
    return AnalysisJob(
        tracked_instrument=tracked_instrument,
        job_type=job_type,
        target_session=target_session,
        status=AnalysisJobStatus.PENDING,
        attempt_count=0,
        created_at=created_at,
        next_attempt_at=created_at,
    )


async def _delete_jobs(
    session: AsyncSession,
    jobs: list[AnalysisJob],
) -> None:
    for job in jobs:
        await session.delete(job)


async def _activate_shared_tracking(
    session: AsyncSession,
    instrument: Instrument,
    target_session: date,
    event_time: datetime,
) -> TrackInstrumentResult:
    tracking = await get_tracking_for_update(session, instrument.id)

    if tracking is not None and tracking.is_active:
        latest_job = await get_latest_technical_job_for_update(
            session,
            tracking.id,
        )
        if not await has_fundamental_snapshot(session, instrument.id):
            active_fundamental_job = (
                await get_active_fundamental_job_for_update(
                    session,
                    tracking.id,
                )
            )
            if active_fundamental_job is None:
                session.add(
                    _new_pending_job(
                        tracking,
                        target_session,
                        event_time,
                        job_type=AnalysisJobType.REFRESH_FUNDAMENTALS,
                    )
                )
                await session.flush()
        return TrackInstrumentResult(
            tracked_instrument=tracking,
            analysis_job=latest_job,
            created=False,
            reactivated=False,
        )

    created = tracking is None
    reactivated = tracking is not None

    if tracking is None:
        tracking = TrackedInstrument(
            instrument=instrument,
            is_active=True,
            operational_state=TrackingOperationalState.PREPARING,
            target_session=target_session,
            created_at=event_time,
            updated_at=event_time,
        )
        session.add(tracking)
    else:
        stale_jobs = await list_active_jobs_for_update(session, tracking.id)
        await _delete_jobs(session, stale_jobs)
        tracking.is_active = True
        tracking.operational_state = TrackingOperationalState.PREPARING
        tracking.target_session = target_session
        tracking.deactivated_at = None
        tracking.reactivated_at = event_time
        tracking.updated_at = event_time
        tracking.terminal_data_error_session = None
        tracking.terminal_data_error_code = None

    technical_job = _new_pending_job(
        tracking,
        target_session,
        event_time,
        job_type=AnalysisJobType.ONBOARD_INSTRUMENT,
    )
    fundamental_job = _new_pending_job(
        tracking,
        target_session,
        event_time,
        job_type=AnalysisJobType.REFRESH_FUNDAMENTALS,
    )
    session.add_all((technical_job, fundamental_job))
    await session.flush()

    return TrackInstrumentResult(
        tracked_instrument=tracking,
        analysis_job=technical_job,
        created=created,
        reactivated=reactivated,
    )


async def add_or_reactivate_instrument(
    session: AsyncSession,
    instrument_id: int,
    target_session: date,
    *,
    occurred_at: datetime | None = None,
) -> TrackInstrumentResult:
    event_time = _event_time(occurred_at)

    async with session.begin():
        instrument = await get_instrument_for_update(
            session,
            instrument_id,
        )
        if instrument is None:
            raise InstrumentNotFoundError(instrument_id)

        return await _activate_shared_tracking(
            session,
            instrument,
            target_session,
            event_time,
        )


async def add_watchlist_memberships(
    session: AsyncSession,
    *,
    user_id: int,
    instrument_ids: list[int],
    target_session: date,
    normal_user_limit: int,
    telegram_notifications_enabled: bool = False,
    occurred_at: datetime | None = None,
) -> AddMembershipsResult:
    event_time = _event_time(occurred_at)
    unique_ids = list(dict.fromkeys(instrument_ids))
    if not unique_ids:
        raise ValueError("At least one instrument is required.")

    async with session.begin():
        user = await get_user_for_update(session, user_id)
        if user is None or not user.is_active:
            raise WatchlistUserNotFoundError()

        instruments: dict[int, Instrument] = {}
        memberships: dict[int, UserWatchlistItem | None] = {}
        for instrument_id in sorted(unique_ids):
            instrument = await get_instrument_for_update(session, instrument_id)
            if instrument is None:
                raise InstrumentNotFoundError(instrument_id)
            instruments[instrument_id] = instrument
            memberships[instrument_id] = await get_membership_for_update(
                session,
                user_id=user.id,
                instrument_id=instrument_id,
            )

        active_count = await count_active_memberships_for_user(session, user.id)
        requested_count = sum(
            membership is None or not membership.is_active
            for membership in memberships.values()
        )
        watchlist_limit = (
            None if user.role == UserRole.ADMIN else normal_user_limit
        )
        if (
            watchlist_limit is not None
            and active_count + requested_count > watchlist_limit
        ):
            raise WatchlistLimitExceededError(
                limit=watchlist_limit,
                active_count=active_count,
                requested_count=requested_count,
            )

        results_by_id: dict[int, AddMembershipResult] = {}
        for instrument_id in sorted(unique_ids):
            membership = memberships[instrument_id]
            membership_created = membership is None
            membership_reactivated = (
                membership is not None and not membership.is_active
            )
            if membership is None:
                baseline_close = await get_close_for_session(
                    session,
                    instrument_id=instrument_id,
                    trading_session=target_session,
                )
                membership = UserWatchlistItem(
                    user_id=user.id,
                    instrument_id=instrument_id,
                    is_active=True,
                    created_at=event_time,
                    updated_at=event_time,
                    baseline_session=target_session,
                    baseline_close_price=baseline_close,
                    telegram_setup_alert_pending=(
                        telegram_notifications_enabled
                    ),
                )
                session.add(membership)
            elif membership_reactivated:
                baseline_close = await get_close_for_session(
                    session,
                    instrument_id=instrument_id,
                    trading_session=target_session,
                )
                membership.is_active = True
                membership.deactivated_at = None
                membership.reactivated_at = event_time
                membership.updated_at = event_time
                membership.baseline_session = target_session
                membership.baseline_close_price = baseline_close
                membership.telegram_setup_alert_pending = (
                    telegram_notifications_enabled
                )

            tracking = await _activate_shared_tracking(
                session,
                instruments[instrument_id],
                target_session,
                event_time,
            )
            if (
                telegram_notifications_enabled
                and (membership_created or membership_reactivated)
            ):
                analysis_available = (
                    await enqueue_existing_watchlist_setup_notification(
                        session,
                        user_id=user.id,
                        instrument_id=instrument_id,
                        target_session=target_session,
                        created_at=event_time,
                    )
                )
                if analysis_available:
                    membership.telegram_setup_alert_pending = False
            results_by_id[instrument_id] = AddMembershipResult(
                membership=membership,
                tracking=tracking,
                membership_created=membership_created,
                membership_reactivated=membership_reactivated,
            )

        await session.flush()
        return AddMembershipsResult(
            user=user,
            items=[results_by_id[item_id] for item_id in unique_ids],
            active_count=active_count + requested_count,
            watchlist_limit=watchlist_limit,
        )


async def deactivate_instrument(
    session: AsyncSession,
    instrument_id: int,
    *,
    occurred_at: datetime | None = None,
) -> DeactivateInstrumentResult:
    event_time = _event_time(occurred_at)

    async with session.begin():
        tracking = await get_tracking_for_update(
            session,
            instrument_id,
        )
        if tracking is None:
            raise TrackedInstrumentNotFoundError(instrument_id)

        if not tracking.is_active:
            return DeactivateInstrumentResult(
                tracked_instrument=tracking,
                cancelled_job_count=0,
                already_inactive=True,
            )

        active_jobs = await list_active_jobs_for_update(
            session,
            tracking.id,
        )
        await _delete_jobs(session, active_jobs)
        tracking.is_active = False
        tracking.deactivated_at = event_time
        tracking.updated_at = event_time
        await session.flush()

        return DeactivateInstrumentResult(
            tracked_instrument=tracking,
            cancelled_job_count=len(active_jobs),
            already_inactive=False,
        )


async def remove_watchlist_membership(
    session: AsyncSession,
    *,
    user_id: int,
    instrument_id: int,
    normal_user_limit: int,
    occurred_at: datetime | None = None,
) -> RemoveMembershipResult:
    event_time = _event_time(occurred_at)

    async with session.begin():
        user = await get_user_for_update(session, user_id)
        if user is None or not user.is_active:
            raise WatchlistUserNotFoundError()

        membership = await get_membership_for_update(
            session,
            user_id=user.id,
            instrument_id=instrument_id,
        )
        if membership is None or not membership.is_active:
            raise WatchlistMembershipNotFoundError(instrument_id)

        tracking = await get_tracking_for_update(session, instrument_id)
        if tracking is None:
            raise TrackedInstrumentNotFoundError(instrument_id)

        membership.is_active = False
        membership.deactivated_at = event_time
        membership.updated_at = event_time
        await session.flush()

        remaining_follower_count = (
            await count_active_followers_for_instrument(session, instrument_id)
        )
        shared_tracking_stopped = False
        cancelled_job_count = 0
        if remaining_follower_count == 0 and tracking.is_active:
            active_jobs = await list_active_jobs_for_update(session, tracking.id)
            await _delete_jobs(session, active_jobs)
            tracking.is_active = False
            tracking.deactivated_at = event_time
            tracking.updated_at = event_time
            shared_tracking_stopped = True
            cancelled_job_count = len(active_jobs)

        active_count = await count_active_memberships_for_user(session, user.id)
        await session.flush()
        return RemoveMembershipResult(
            membership=membership,
            tracked_instrument=tracking,
            active_count=active_count,
            watchlist_limit=(
                None if user.role == UserRole.ADMIN else normal_user_limit
            ),
            remaining_follower_count=remaining_follower_count,
            shared_tracking_stopped=shared_tracking_stopped,
            cancelled_job_count=cancelled_job_count,
        )


async def purge_instrument_for_admin(
    session: AsyncSession,
    *,
    user_id: int,
    instrument_id: int,
) -> PurgeInstrumentResult:
    async with session.begin():
        user = await get_user_for_update(session, user_id)
        if user is None or not user.is_active or user.role != UserRole.ADMIN:
            raise WatchlistUserNotFoundError()

        instrument = await get_instrument_for_update(session, instrument_id)
        if instrument is None:
            raise InstrumentNotFoundError(instrument_id)
        company_id = instrument.company_id

        await session.execute(
            delete(Instrument).where(Instrument.id == instrument_id)
        )
        deleted_company = await session.execute(
            delete(Company).where(
                Company.id == company_id,
                ~select(Instrument.id)
                .where(Instrument.company_id == Company.id)
                .exists(),
            )
        )
        active_count = await count_active_memberships_for_user(session, user.id)
        await session.flush()
        return PurgeInstrumentResult(
            instrument_id=instrument_id,
            active_count=active_count,
            company_removed=deleted_company.rowcount == 1,
        )


async def get_watchlist(
    session: AsyncSession,
    user_id: int,
) -> list[WatchlistRecord]:
    return await list_watchlist_records(session, user_id)
