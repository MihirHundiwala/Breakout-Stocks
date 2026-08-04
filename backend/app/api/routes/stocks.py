from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_user_session
from app.db.session import get_db_session
from app.models import UserSession
from app.schemas.stocks import (
    AnalysisChartResponse,
    StockDetailResponse,
    StockListResponse,
)
from app.services.stocks import (
    StockAnalysisNotFoundError,
    StockChartNotFoundError,
    get_stock_chart,
    get_stock_detail,
    get_stock_list,
)


router = APIRouter(prefix="/stocks", tags=["stocks"])
StockPageSize = Literal["10", "25", "50", "100", "all"]


@router.get(
    "/{instrument_id}/chart",
    response_model=AnalysisChartResponse,
    status_code=status.HTTP_200_OK,
    summary="Get immutable chart evidence for the latest analysis",
)
async def stock_chart(
    instrument_id: Annotated[int, Path(ge=1)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user_session: Annotated[UserSession, Depends(require_user_session)],
) -> AnalysisChartResponse:
    try:
        return await get_stock_chart(
            session,
            instrument_id,
            user_id=user_session.user_id,
            is_admin=user_session.user.role.value == "ADMIN",
        )
    except StockChartNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="STOCK_CHART_NOT_FOUND",
        ) from error


@router.get(
    "",
    response_model=StockListResponse,
    status_code=status.HTTP_200_OK,
    summary="List stocks with their latest valid analysis",
)
async def list_stocks(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user_session: Annotated[UserSession, Depends(require_user_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    search: Annotated[str | None, Query(max_length=100)] = None,
    sort: Annotated[
        Literal[
            "status",
            "market_cap_desc",
            "market_cap_asc",
            "day_change_desc",
            "day_change_asc",
            "watchlist_change_desc",
            "watchlist_change_asc",
        ],
        Query(),
    ] = "status",
    page_size: Annotated[StockPageSize, Query()] = "50",
) -> StockListResponse:
    return await get_stock_list(
        session,
        user_id=user_session.user_id,
        is_admin=user_session.user.role.value == "ADMIN",
        page=page,
        page_size=(None if page_size == "all" else int(page_size)),
        search=search,
        sort=sort,
    )


@router.get(
    "/{instrument_id}",
    response_model=StockDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the latest persisted research for one stock",
)
async def stock_detail(
    instrument_id: Annotated[int, Path(ge=1)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user_session: Annotated[UserSession, Depends(require_user_session)],
) -> StockDetailResponse:
    try:
        return await get_stock_detail(
            session,
            instrument_id,
            user_id=user_session.user_id,
            is_admin=user_session.user.role.value == "ADMIN",
        )
    except StockAnalysisNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="STOCK_ANALYSIS_NOT_FOUND",
        ) from error
