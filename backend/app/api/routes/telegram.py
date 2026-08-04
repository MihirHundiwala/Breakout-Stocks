from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    require_user_csrf,
    require_user_session,
)
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.models import UserSession
from app.schemas.telegram import (
    TelegramConnectionResponse,
    TelegramLinkResponse,
)
from app.services.telegram_connections import (
    InvalidTelegramUsernameError,
    create_telegram_link,
    disconnect_telegram,
    get_telegram_connection,
)


router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.get("/connection", response_model=TelegramConnectionResponse)
async def read_telegram_connection(
    user_session: Annotated[UserSession, Depends(require_user_session)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TelegramConnectionResponse:
    connection = await get_telegram_connection(
        session,
        user_id=user_session.user_id,
    )
    return TelegramConnectionResponse(
        available=settings.telegram_notifications_enabled,
        connected=connection.connected,
        pending=connection.pending,
        username=connection.username,
    )


@router.post("/connection", response_model=TelegramLinkResponse)
async def connect_telegram(
    user_session: Annotated[UserSession, Depends(require_user_csrf)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TelegramLinkResponse:
    if (
        not settings.telegram_notifications_enabled
        or settings.telegram_bot_username is None
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TELEGRAM_NOT_CONFIGURED",
        )
    try:
        result = await create_telegram_link(
            session,
            user_id=user_session.user_id,
            bot_username=settings.telegram_bot_username,
        )
    except InvalidTelegramUsernameError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="INVALID_TELEGRAM_USERNAME",
        ) from error
    return TelegramLinkResponse(
        available=True,
        connected=result.connection.connected,
        pending=result.connection.pending,
        username=result.connection.username,
        bot_url=result.bot_url,
        expires_at=result.expires_at,
    )


@router.delete("/connection", status_code=status.HTTP_204_NO_CONTENT)
async def remove_telegram_connection(
    user_session: Annotated[UserSession, Depends(require_user_csrf)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    await disconnect_telegram(session, user_id=user_session.user_id)
