from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models import TrackingOperationalState


Isin = Annotated[str, Field(pattern=r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")]


class BatchAddWatchlistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    isins: list[Isin] = Field(min_length=1, max_length=50)


class InstrumentCandidateResponse(BaseModel):
    company_name: str
    exchange: str
    trading_symbol: str
    isin: str


class InstrumentSearchResponse(BaseModel):
    items: list[InstrumentCandidateResponse]
    count: int


class WatchlistItemResponse(BaseModel):
    instrument_id: int
    company_name: str
    exchange: str
    trading_symbol: str
    market_data_state: TrackingOperationalState
    target_session: date
    added_at: datetime
    baseline_session: date
    baseline_close_price: Decimal | None
    latest_close_price: Decimal | None
    movement_since_added_percent: Decimal | None


class WatchlistResponse(BaseModel):
    items: list[WatchlistItemResponse]
    count: int
    watchlist_limit: int | None
    remaining_slots: int | None


class AddedWatchlistItemResponse(BaseModel):
    instrument_id: int
    membership_created: bool
    membership_reactivated: bool
    already_in_watchlist: bool
    shared_analysis_started: bool


class BatchAddWatchlistResponse(BaseModel):
    items: list[AddedWatchlistItemResponse]
    active_count: int
    watchlist_limit: int | None
    remaining_slots: int | None


class RemoveWatchlistItemResponse(BaseModel):
    instrument_id: int
    removed: bool
    active_count: int
    watchlist_limit: int | None
    remaining_slots: int | None


class RefreshWatchlistResponse(BaseModel):
    target_session: date
    scheduled_count: int
    already_updating_count: int
    already_current_count: int
    terminal_data_failure_count: int
