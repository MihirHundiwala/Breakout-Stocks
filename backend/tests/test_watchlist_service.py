from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalysisJob,
    AnalysisJobStatus,
    AnalysisJobType,
    AnalysisSnapshot,
    AppUser,
    Company,
    DailyCandle,
    FundamentalCoverageStatus,
    FundamentalPeriod,
    FundamentalPeriodKind,
    FundamentalSnapshot,
    Instrument,
    ProviderInstrumentIdentity,
    StatementBasis,
    TechnicalStatus,
    TelegramConnection,
    TelegramNotification,
    TrackedInstrument,
    TrackingOperationalState,
    UserRole,
    UserWatchlistItem,
)
from app.services import watchlist as watchlist_service
from app.services.watchlist import (
    InstrumentNotFoundError,
    TrackedInstrumentNotFoundError,
    WatchlistLimitExceededError,
    add_watchlist_memberships,
    add_or_reactivate_instrument,
    deactivate_instrument,
    ensure_upstox_instrument,
    purge_instrument_for_admin,
    remove_watchlist_membership,
    _provider_identity_lock_key,
)
from app.providers.contracts import InstrumentCandidate


ADDED_AT = datetime(2026, 7, 25, 10, 0, tzinfo=UTC)
DEACTIVATED_AT = datetime(2026, 7, 25, 11, 0, tzinfo=UTC)
REACTIVATED_AT = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
FIRST_TARGET_SESSION = date(2026, 7, 24)
NEXT_TARGET_SESSION = date(2026, 7, 25)


async def persist_instrument(
    session: AsyncSession,
    symbol: str = "EXAMPLE",
) -> Instrument:
    instrument = Instrument(
        company=Company(name=f"{symbol} Industries Limited"),
        exchange="NSE",
        trading_symbol=symbol,
    )
    session.add(instrument)
    await session.commit()
    return instrument


async def persist_user(
    session: AsyncSession,
    username: str,
    role: UserRole = UserRole.USER,
) -> AppUser:
    user = AppUser(
        username=username,
        role=role,
        password_hash=("$argon2id$synthetic" if role == UserRole.USER else None),
    )
    session.add(user)
    await session.commit()
    return user


def test_provider_identity_lock_key_is_stable_and_signed() -> None:
    first = _provider_identity_lock_key("UPSTOX", "INE123A01010")
    repeated = _provider_identity_lock_key("UPSTOX", "INE123A01010")
    different = _provider_identity_lock_key("UPSTOX", "INE123A01011")

    assert first == repeated
    assert first != different
    assert -(2**63) <= first < 2**63


@pytest.mark.anyio
async def test_new_membership_queues_fresh_stored_setup_alert(
    db_session: AsyncSession,
) -> None:
    user = await persist_user(db_session, "telegram-follower")
    instrument = await persist_instrument(db_session, "STOREDSETUP")
    user_id = user.id
    instrument_id = instrument.id
    db_session.add_all((
        TelegramConnection(
            user_id=user_id,
            telegram_chat_id="991",
            telegram_username="storedsetup",
            connected_at=ADDED_AT,
            updated_at=ADDED_AT,
        ),
        AnalysisSnapshot(
            instrument_id=instrument_id,
            analysis_date=FIRST_TARGET_SESSION,
            technical_status=TechnicalStatus.CONSOLIDATING,
            fundamental_coverage=FundamentalCoverageStatus.UNKNOWN,
            close_price=Decimal("101"),
            previous_close_price=Decimal("100"),
            source="UPSTOX",
            source_fetched_at=ADDED_AT,
            algorithm_version="stored-setup-v1",
            candle_revision="stored-setup-r1",
            generated_at=ADDED_AT,
        ),
    ))
    await db_session.commit()

    result = await add_watchlist_memberships(
        db_session,
        user_id=user_id,
        instrument_ids=[instrument_id],
        target_session=FIRST_TARGET_SESSION,
        normal_user_limit=20,
        telegram_notifications_enabled=True,
        occurred_at=ADDED_AT + timedelta(minutes=1),
    )

    notification = await db_session.scalar(select(TelegramNotification))
    assert notification is not None
    assert notification.user_id == user_id
    assert notification.event_kind == "WATCHLIST_ADDED"
    assert result.items[0].membership.telegram_setup_alert_pending is False
    await db_session.rollback()

    repeated = await add_watchlist_memberships(
        db_session,
        user_id=user_id,
        instrument_ids=[instrument_id],
        target_session=FIRST_TARGET_SESSION,
        normal_user_limit=20,
        telegram_notifications_enabled=True,
        occurred_at=ADDED_AT + timedelta(minutes=2),
    )
    notification_count = await db_session.scalar(
        select(func.count()).select_from(TelegramNotification)
    )
    assert repeated.items[0].membership_created is False
    assert repeated.items[0].membership_reactivated is False
    assert notification_count == 1


@pytest.mark.anyio
async def test_two_users_share_one_tracking_and_last_removal_stops_it(
    db_session: AsyncSession,
) -> None:
    first_user = await persist_user(db_session, "first-user")
    second_user = await persist_user(db_session, "second-user")
    instrument = await persist_instrument(db_session)
    first_user_id = first_user.id
    second_user_id = second_user.id
    instrument_id = instrument.id

    first_add = await add_watchlist_memberships(
        db_session,
        user_id=first_user_id,
        instrument_ids=[instrument_id],
        target_session=FIRST_TARGET_SESSION,
        normal_user_limit=20,
        occurred_at=ADDED_AT,
    )
    second_add = await add_watchlist_memberships(
        db_session,
        user_id=second_user_id,
        instrument_ids=[instrument_id],
        target_session=FIRST_TARGET_SESSION,
        normal_user_limit=20,
        occurred_at=ADDED_AT + timedelta(minutes=1),
    )

    assert first_add.items[0].tracking.created is True
    assert first_add.items[0].membership.baseline_session == FIRST_TARGET_SESSION
    assert first_add.items[0].membership.baseline_close_price is None
    assert second_add.items[0].tracking.created is False
    assert second_add.items[0].tracking.reactivated is False
    assert await db_session.scalar(
        select(func.count()).select_from(UserWatchlistItem)
    ) == 2
    assert await db_session.scalar(
        select(func.count()).select_from(TrackedInstrument)
    ) == 1
    assert await db_session.scalar(
        select(func.count()).select_from(AnalysisJob)
    ) == 2
    await db_session.rollback()

    first_removal = await remove_watchlist_membership(
        db_session,
        user_id=first_user_id,
        instrument_id=instrument_id,
        normal_user_limit=20,
        occurred_at=DEACTIVATED_AT,
    )
    assert first_removal.remaining_follower_count == 1
    assert first_removal.shared_tracking_stopped is False
    assert first_removal.cancelled_job_count == 0
    assert first_removal.tracked_instrument.is_active is True

    final_removal = await remove_watchlist_membership(
        db_session,
        user_id=second_user_id,
        instrument_id=instrument_id,
        normal_user_limit=20,
        occurred_at=DEACTIVATED_AT + timedelta(minutes=1),
    )
    assert final_removal.remaining_follower_count == 0
    assert final_removal.shared_tracking_stopped is True
    assert final_removal.cancelled_job_count == 2
    assert final_removal.tracked_instrument.is_active is False


@pytest.mark.anyio
async def test_add_to_active_tracking_queues_missing_fundamentals(
    db_session: AsyncSession,
) -> None:
    first_user = await persist_user(db_session, "fundamental-owner")
    second_user = await persist_user(db_session, "fundamental-follower")
    instrument = await persist_instrument(db_session, "NEEDSFUND")

    first_add = await add_watchlist_memberships(
        db_session,
        user_id=first_user.id,
        instrument_ids=[instrument.id],
        target_session=FIRST_TARGET_SESSION,
        normal_user_limit=20,
        occurred_at=ADDED_AT,
    )
    fundamental_job = await db_session.scalar(
        select(AnalysisJob).where(
            AnalysisJob.job_type == AnalysisJobType.REFRESH_FUNDAMENTALS
        )
    )
    assert fundamental_job is not None
    await db_session.delete(fundamental_job)
    await db_session.commit()

    await add_watchlist_memberships(
        db_session,
        user_id=second_user.id,
        instrument_ids=[instrument.id],
        target_session=FIRST_TARGET_SESSION,
        normal_user_limit=20,
        occurred_at=ADDED_AT + timedelta(minutes=1),
    )

    fundamental_jobs = list(
        await db_session.scalars(
            select(AnalysisJob).where(
                AnalysisJob.job_type
                == AnalysisJobType.REFRESH_FUNDAMENTALS
            )
        )
    )
    assert len(fundamental_jobs) == 1
    assert (
        fundamental_jobs[0].tracked_instrument_id
        == first_add.items[0].tracking.tracked_instrument.id
    )


@pytest.mark.anyio
async def test_add_to_active_tracking_does_not_duplicate_fundamental_job(
    db_session: AsyncSession,
) -> None:
    first_user = await persist_user(db_session, "queued-owner")
    second_user = await persist_user(db_session, "queued-follower")
    instrument = await persist_instrument(db_session, "QUEUEDFUND")

    await add_watchlist_memberships(
        db_session,
        user_id=first_user.id,
        instrument_ids=[instrument.id],
        target_session=FIRST_TARGET_SESSION,
        normal_user_limit=20,
        occurred_at=ADDED_AT,
    )
    await add_watchlist_memberships(
        db_session,
        user_id=second_user.id,
        instrument_ids=[instrument.id],
        target_session=FIRST_TARGET_SESSION,
        normal_user_limit=20,
        occurred_at=ADDED_AT + timedelta(minutes=1),
    )

    fundamental_job_count = await db_session.scalar(
        select(func.count())
        .select_from(AnalysisJob)
        .where(AnalysisJob.job_type == AnalysisJobType.REFRESH_FUNDAMENTALS)
    )
    assert fundamental_job_count == 1


@pytest.mark.anyio
async def test_readding_resets_membership_price_baseline(
    db_session: AsyncSession,
) -> None:
    user = await persist_user(db_session, "baseline-user")
    instrument = await persist_instrument(db_session)
    db_session.add_all(
        [
            DailyCandle(
                instrument_id=instrument.id,
                trading_date=FIRST_TARGET_SESSION,
                open_price=Decimal("98"),
                high_price=Decimal("102"),
                low_price=Decimal("97"),
                close_price=Decimal("100"),
                volume=1_000,
                open_interest=0,
                source="UPSTOX",
                source_timestamp=ADDED_AT,
                fetched_at=ADDED_AT,
            ),
            DailyCandle(
                instrument_id=instrument.id,
                trading_date=NEXT_TARGET_SESSION,
                open_price=Decimal("118"),
                high_price=Decimal("122"),
                low_price=Decimal("117"),
                close_price=Decimal("120"),
                volume=1_200,
                open_interest=0,
                source="UPSTOX",
                source_timestamp=REACTIVATED_AT,
                fetched_at=REACTIVATED_AT,
            ),
        ]
    )
    await db_session.commit()

    initial = await add_watchlist_memberships(
        db_session,
        user_id=user.id,
        instrument_ids=[instrument.id],
        target_session=FIRST_TARGET_SESSION,
        normal_user_limit=20,
        occurred_at=ADDED_AT,
    )
    assert initial.items[0].membership.baseline_close_price == Decimal("100")
    await remove_watchlist_membership(
        db_session,
        user_id=user.id,
        instrument_id=instrument.id,
        normal_user_limit=20,
        occurred_at=DEACTIVATED_AT,
    )

    readded = await add_watchlist_memberships(
        db_session,
        user_id=user.id,
        instrument_ids=[instrument.id],
        target_session=NEXT_TARGET_SESSION,
        normal_user_limit=20,
        occurred_at=REACTIVATED_AT,
    )

    membership = readded.items[0].membership
    assert readded.items[0].membership_reactivated is True
    assert membership.baseline_session == NEXT_TARGET_SESSION
    assert membership.baseline_close_price == Decimal("120")
    assert membership.reactivated_at == REACTIVATED_AT


@pytest.mark.anyio
async def test_normal_user_batch_over_limit_rolls_back_every_membership(
    db_session: AsyncSession,
) -> None:
    user = await persist_user(db_session, "limited-user")
    first = await persist_instrument(db_session, "FIRST")
    second = await persist_instrument(db_session, "SECOND")

    with pytest.raises(WatchlistLimitExceededError) as error:
        await add_watchlist_memberships(
            db_session,
            user_id=user.id,
            instrument_ids=[first.id, second.id],
            target_session=FIRST_TARGET_SESSION,
            normal_user_limit=1,
            occurred_at=ADDED_AT,
        )

    assert error.value.limit == 1
    assert error.value.active_count == 0
    assert error.value.requested_count == 2
    assert await db_session.scalar(
        select(func.count()).select_from(UserWatchlistItem)
    ) == 0
    assert await db_session.scalar(
        select(func.count()).select_from(TrackedInstrument)
    ) == 0
    assert await db_session.scalar(
        select(func.count()).select_from(AnalysisJob)
    ) == 0


@pytest.mark.anyio
async def test_admin_is_not_limited_by_normal_user_quota(
    db_session: AsyncSession,
) -> None:
    admin = await persist_user(db_session, "admin", UserRole.ADMIN)
    first = await persist_instrument(db_session, "FIRST")
    second = await persist_instrument(db_session, "SECOND")

    result = await add_watchlist_memberships(
        db_session,
        user_id=admin.id,
        instrument_ids=[first.id, second.id],
        target_session=FIRST_TARGET_SESSION,
        normal_user_limit=1,
        occurred_at=ADDED_AT,
    )

    assert result.active_count == 2
    assert result.watchlist_limit is None
    assert len(result.items) == 2


@pytest.mark.anyio
async def test_admin_purge_removes_all_data_and_allows_clean_readd(
    db_session: AsyncSession,
) -> None:
    admin = await persist_user(db_session, "purge-admin", UserRole.ADMIN)
    follower = await persist_user(db_session, "purge-follower")
    instrument = await persist_instrument(db_session, "PURGE")
    instrument_id = instrument.id
    company_id = instrument.company_id

    for user in (admin, follower):
        await add_watchlist_memberships(
            db_session,
            user_id=user.id,
            instrument_ids=[instrument_id],
            target_session=FIRST_TARGET_SESSION,
            normal_user_limit=20,
            occurred_at=ADDED_AT,
        )

    db_session.add_all(
        [
            ProviderInstrumentIdentity(
                instrument_id=instrument_id,
                provider="UPSTOX",
                instrument_key="NSE_EQ|INE123A01010",
                isin="INE123A01010",
                effective_from=FIRST_TARGET_SESSION,
                source_fetched_at=ADDED_AT,
            ),
            DailyCandle(
                instrument_id=instrument_id,
                trading_date=FIRST_TARGET_SESSION,
                open_price=Decimal("99"),
                high_price=Decimal("101"),
                low_price=Decimal("98"),
                close_price=Decimal("100"),
                volume=1000,
                open_interest=0,
                source="UPSTOX",
                source_timestamp=ADDED_AT,
                fetched_at=ADDED_AT,
            ),
            AnalysisSnapshot(
                instrument_id=instrument_id,
                analysis_date=FIRST_TARGET_SESSION,
                technical_status=TechnicalStatus.NO_SETUP,
                fundamental_coverage=FundamentalCoverageStatus.UNKNOWN,
                close_price=Decimal("100"),
                previous_close_price=Decimal("99"),
                source="UPSTOX",
                source_fetched_at=ADDED_AT,
                algorithm_version="purge-test-v1",
                candle_revision="purge-test-r1",
                generated_at=ADDED_AT,
            ),
            FundamentalSnapshot(
                instrument_id=instrument_id,
                as_of_date=FIRST_TARGET_SESSION,
                coverage=FundamentalCoverageStatus.UNKNOWN,
                available_metric_count=0,
                expected_metric_count=1,
                metrics={},
                source="UPSTOX",
                source_fetched_at=ADDED_AT,
                schema_version="purge-test-v1",
            ),
            FundamentalPeriod(
                company_id=company_id,
                period_end=date(2026, 3, 31),
                period_kind=FundamentalPeriodKind.YEARLY,
                statement_basis=StatementBasis.CONSOLIDATED,
                currency="INR",
                metrics={"revenue": "100"},
                source="UPSTOX",
                source_fetched_at=ADDED_AT,
                schema_version="purge-test-v1",
            ),
        ]
    )
    await db_session.commit()

    result = await purge_instrument_for_admin(
        db_session,
        user_id=admin.id,
        instrument_id=instrument_id,
    )

    assert result.active_count == 0
    assert result.company_removed is True
    for model in (
        AnalysisJob,
        AnalysisSnapshot,
        DailyCandle,
        FundamentalSnapshot,
        FundamentalPeriod,
        ProviderInstrumentIdentity,
        TrackedInstrument,
        UserWatchlistItem,
        Instrument,
        Company,
    ):
        assert await db_session.scalar(select(func.count()).select_from(model)) == 0
    await db_session.commit()

    recreated = await ensure_upstox_instrument(
        db_session,
        InstrumentCandidate(
            company_name="Purge Industries Limited",
            exchange="NSE",
            trading_symbol="PURGE",
            isin="INE123A01010",
            instrument_key="NSE_EQ|INE123A01010",
        ),
        fetched_at=REACTIVATED_AT,
    )
    readded = await add_watchlist_memberships(
        db_session,
        user_id=admin.id,
        instrument_ids=[recreated.id],
        target_session=NEXT_TARGET_SESSION,
        normal_user_limit=20,
        occurred_at=REACTIVATED_AT,
    )

    assert recreated.id != instrument_id
    assert readded.items[0].tracking.analysis_job is not None
    assert readded.items[0].tracking.analysis_job.status == AnalysisJobStatus.PENDING


@pytest.mark.anyio
async def test_add_creates_tracking_and_pending_job_atomically(
    db_session: AsyncSession,
) -> None:
    instrument = await persist_instrument(db_session)

    result = await add_or_reactivate_instrument(
        db_session,
        instrument.id,
        FIRST_TARGET_SESSION,
        occurred_at=ADDED_AT,
    )

    assert result.created is True
    assert result.reactivated is False
    assert result.analysis_job is not None
    assert result.tracked_instrument.is_active is True
    assert (
        result.tracked_instrument.operational_state
        == TrackingOperationalState.PREPARING
    )
    assert (
        result.tracked_instrument.target_session
        == FIRST_TARGET_SESSION
    )
    assert result.analysis_job.status == AnalysisJobStatus.PENDING
    assert result.analysis_job.job_type == AnalysisJobType.ONBOARD_INSTRUMENT
    assert (
        result.analysis_job.target_session
        == FIRST_TARGET_SESSION
    )
    assert set(await db_session.scalars(select(AnalysisJob.job_type))) == {
        AnalysisJobType.ONBOARD_INSTRUMENT,
        AnalysisJobType.REFRESH_FUNDAMENTALS,
    }


@pytest.mark.anyio
async def test_repeated_add_returns_existing_tracking_and_job(
    db_session: AsyncSession,
) -> None:
    instrument = await persist_instrument(db_session)
    first_result = await add_or_reactivate_instrument(
        db_session,
        instrument.id,
        FIRST_TARGET_SESSION,
        occurred_at=ADDED_AT,
    )

    second_result = await add_or_reactivate_instrument(
        db_session,
        instrument.id,
        FIRST_TARGET_SESSION,
        occurred_at=ADDED_AT + timedelta(minutes=1),
    )

    tracking_count = await db_session.scalar(
        select(func.count()).select_from(TrackedInstrument)
    )
    job_count = await db_session.scalar(
        select(func.count()).select_from(AnalysisJob)
    )
    assert second_result.created is False
    assert second_result.reactivated is False
    assert (
        second_result.tracked_instrument.id
        == first_result.tracked_instrument.id
    )
    assert second_result.analysis_job is not None
    assert first_result.analysis_job is not None
    assert (
        second_result.analysis_job.id
        == first_result.analysis_job.id
    )
    assert tracking_count == 1
    assert job_count == 2


@pytest.mark.anyio
async def test_reactivation_reuses_tracking_and_creates_new_job(
    db_session: AsyncSession,
) -> None:
    instrument = await persist_instrument(db_session)
    initial = await add_or_reactivate_instrument(
        db_session,
        instrument.id,
        FIRST_TARGET_SESSION,
        occurred_at=ADDED_AT,
    )
    await deactivate_instrument(
        db_session,
        instrument.id,
        occurred_at=DEACTIVATED_AT,
    )

    reactivated = await add_or_reactivate_instrument(
        db_session,
        instrument.id,
        NEXT_TARGET_SESSION,
        occurred_at=REACTIVATED_AT,
    )

    job_count = await db_session.scalar(
        select(func.count()).select_from(AnalysisJob)
    )
    assert reactivated.created is False
    assert reactivated.reactivated is True
    assert (
        reactivated.tracked_instrument.id
        == initial.tracked_instrument.id
    )
    assert reactivated.tracked_instrument.is_active is True
    assert reactivated.tracked_instrument.deactivated_at is None
    assert (
        reactivated.tracked_instrument.reactivated_at
        == REACTIVATED_AT
    )
    assert (
        reactivated.tracked_instrument.target_session
        == NEXT_TARGET_SESSION
    )
    assert initial.analysis_job is not None
    assert reactivated.analysis_job is not None
    assert reactivated.analysis_job.status == AnalysisJobStatus.PENDING
    assert reactivated.analysis_job.id != initial.analysis_job.id
    assert job_count == 2


@pytest.mark.anyio
@pytest.mark.parametrize(
    "job_status",
    [AnalysisJobStatus.PENDING, AnalysisJobStatus.RUNNING],
)
async def test_deactivation_cancels_active_job(
    db_session: AsyncSession,
    job_status: AnalysisJobStatus,
) -> None:
    instrument = await persist_instrument(db_session)
    added = await add_or_reactivate_instrument(
        db_session,
        instrument.id,
        FIRST_TARGET_SESSION,
        occurred_at=ADDED_AT,
    )
    assert added.analysis_job is not None

    if job_status == AnalysisJobStatus.RUNNING:
        async with db_session.begin():
            added.analysis_job.status = AnalysisJobStatus.RUNNING
            added.analysis_job.started_at = ADDED_AT + timedelta(
                minutes=1
            )

    result = await deactivate_instrument(
        db_session,
        instrument.id,
        occurred_at=DEACTIVATED_AT,
    )

    assert result.already_inactive is False
    assert result.cancelled_job_count == 2
    assert result.tracked_instrument.is_active is False
    assert (
        result.tracked_instrument.deactivated_at
        == DEACTIVATED_AT
    )
    assert await db_session.get(AnalysisJob, added.analysis_job.id) is None


@pytest.mark.anyio
async def test_repeated_deactivation_is_idempotent(
    db_session: AsyncSession,
) -> None:
    instrument = await persist_instrument(db_session)
    await add_or_reactivate_instrument(
        db_session,
        instrument.id,
        FIRST_TARGET_SESSION,
        occurred_at=ADDED_AT,
    )
    await deactivate_instrument(
        db_session,
        instrument.id,
        occurred_at=DEACTIVATED_AT,
    )

    repeated = await deactivate_instrument(
        db_session,
        instrument.id,
        occurred_at=DEACTIVATED_AT + timedelta(minutes=1),
    )

    assert repeated.already_inactive is True
    assert repeated.cancelled_job_count == 0
    assert (
        repeated.tracked_instrument.deactivated_at
        == DEACTIVATED_AT
    )


@pytest.mark.anyio
async def test_add_rejects_unknown_instrument_without_writes(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(InstrumentNotFoundError):
        await add_or_reactivate_instrument(
            db_session,
            999_999,
            FIRST_TARGET_SESSION,
            occurred_at=ADDED_AT,
        )

    tracking_count = await db_session.scalar(
        select(func.count()).select_from(TrackedInstrument)
    )
    job_count = await db_session.scalar(
        select(func.count()).select_from(AnalysisJob)
    )
    assert tracking_count == 0
    assert job_count == 0


@pytest.mark.anyio
async def test_deactivate_rejects_untracked_instrument(
    db_session: AsyncSession,
) -> None:
    instrument = await persist_instrument(db_session)

    with pytest.raises(TrackedInstrumentNotFoundError):
        await deactivate_instrument(
            db_session,
            instrument.id,
            occurred_at=DEACTIVATED_AT,
        )


@pytest.mark.anyio
async def test_add_rejects_naive_event_timestamp(
    db_session: AsyncSession,
) -> None:
    instrument = await persist_instrument(db_session)

    with pytest.raises(
        ValueError,
        match="Event timestamps must be timezone-aware",
    ):
        await add_or_reactivate_instrument(
            db_session,
            instrument.id,
            FIRST_TARGET_SESSION,
            occurred_at=datetime(2026, 7, 25, 10, 0),
        )

    tracking_count = await db_session.scalar(
        select(func.count()).select_from(TrackedInstrument)
    )
    assert tracking_count == 0


@pytest.mark.anyio
async def test_job_creation_failure_rolls_back_tracking(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instrument = await persist_instrument(db_session)

    def fail_job_creation(*_args: object, **_kwargs: object) -> AnalysisJob:
        raise RuntimeError("Synthetic job creation failure")

    monkeypatch.setattr(
        watchlist_service,
        "_new_pending_job",
        fail_job_creation,
    )

    with pytest.raises(RuntimeError, match="Synthetic job creation failure"):
        await add_or_reactivate_instrument(
            db_session,
            instrument.id,
            FIRST_TARGET_SESSION,
            occurred_at=ADDED_AT,
        )

    tracking_count = await db_session.scalar(
        select(func.count()).select_from(TrackedInstrument)
    )
    job_count = await db_session.scalar(
        select(func.count()).select_from(AnalysisJob)
    )
    assert tracking_count == 0
    assert job_count == 0
