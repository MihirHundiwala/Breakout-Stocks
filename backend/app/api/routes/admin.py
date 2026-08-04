from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_admin_session
from app.db.session import get_db_session
from app.models import UserSession
from app.schemas.admin_analytics import AdminAnalyticsResponse
from app.services.admin_analytics import get_admin_analytics


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/analytics", response_model=AdminAnalyticsResponse)
async def admin_analytics(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _admin: Annotated[UserSession, Depends(require_admin_session)],
) -> AdminAnalyticsResponse:
    return await get_admin_analytics(session)
