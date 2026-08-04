from datetime import datetime

from pydantic import BaseModel


class TelegramConnectionResponse(BaseModel):
    available: bool
    connected: bool
    pending: bool
    username: str | None = None


class TelegramLinkResponse(TelegramConnectionResponse):
    bot_url: str | None = None
    expires_at: datetime | None = None
