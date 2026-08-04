import json
import asyncio
from time import monotonic
from dataclasses import dataclass

import httpx2 as httpx
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.providers.contracts import RequestRateLimiter


TELEGRAM_API_BASE_URL = "https://api.telegram.org"


class _ResponseParameters(BaseModel):
    model_config = ConfigDict(extra="ignore")
    retry_after: int | None = None


class _TelegramResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    ok: bool
    error_code: int | None = None
    description: str | None = None
    parameters: _ResponseParameters | None = None
    result: object | None = None


class TelegramUser(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int
    username: str | None = None


class TelegramChat(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int
    type: str


class TelegramMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    text: str | None = None
    chat: TelegramChat
    sender: TelegramUser | None = Field(default=None, alias="from")


class TelegramUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    update_id: int
    message: TelegramMessage | None = None


@dataclass(frozen=True, slots=True)
class TelegramPhoto:
    filename: str
    content: bytes


class TelegramDeliveryError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        retryable: bool,
        retry_after_seconds: int | None = None,
    ) -> None:
        self.code = code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        super().__init__(code)


class TelegramClient:
    def __init__(
        self,
        *,
        bot_token: str,
        timeout_seconds: float = 15.0,
        client: httpx.AsyncClient | None = None,
        minimum_interval_seconds: float = 1.0,
        request_rate_limiter: RequestRateLimiter | None = None,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._base_url = f"{TELEGRAM_API_BASE_URL}/bot{bot_token}"
        self._minimum_interval_seconds = minimum_interval_seconds
        self._request_rate_limiter = request_rate_limiter
        self._last_request_at: float | None = None
        self._rate_lock = asyncio.Lock()

    async def __aenter__(self) -> "TelegramClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _post(
        self,
        method: str,
        *,
        paced: bool = True,
        **kwargs: object,
    ) -> object | None:
        if paced:
            if self._request_rate_limiter is not None:
                await self._request_rate_limiter.acquire(
                    bucket_key="telegram:bot",
                    minimum_interval_seconds=self._minimum_interval_seconds,
                )
            else:
                async with self._rate_lock:
                    now = monotonic()
                    if self._last_request_at is not None:
                        remaining = (
                            self._minimum_interval_seconds
                            - (now - self._last_request_at)
                        )
                        if remaining > 0:
                            await asyncio.sleep(remaining)
                    self._last_request_at = monotonic()
        try:
            response = await self._client.post(
                f"{self._base_url}/{method}",
                **kwargs,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise TelegramDeliveryError(
                "TELEGRAM_NETWORK_ERROR",
                retryable=True,
            ) from error
        try:
            payload = _TelegramResponse.model_validate(response.json())
        except (ValueError, TypeError) as error:
            raise TelegramDeliveryError(
                "TELEGRAM_INVALID_RESPONSE",
                retryable=response.status_code >= 500,
            ) from error
        if response.status_code < 400 and payload.ok:
            return payload.result
        retry_after = (
            payload.parameters.retry_after if payload.parameters else None
        )
        code = "TELEGRAM_RATE_LIMITED" if response.status_code == 429 else "TELEGRAM_REQUEST_REJECTED"
        raise TelegramDeliveryError(
            code,
            retryable=response.status_code == 429 or response.status_code >= 500,
            retry_after_seconds=retry_after,
        )

    async def send_alert(
        self,
        *,
        chat_id: str,
        caption: str,
        photos: list[TelegramPhoto],
    ) -> None:
        safe_caption = caption[:1024]
        if not photos:
            await self._post(
                "sendMessage",
                data={"chat_id": chat_id, "text": safe_caption},
            )
            return
        if len(photos) == 1:
            photo = photos[0]
            await self._post(
                "sendPhoto",
                data={"chat_id": chat_id, "caption": safe_caption},
                files={"photo": (photo.filename, photo.content, "image/png")},
            )
            return
        bounded_photos = photos[:10]
        media = [
            {
                "type": "photo",
                "media": f"attach://chart_{index}",
                **({"caption": safe_caption} if index == 0 else {}),
            }
            for index, _ in enumerate(bounded_photos)
        ]
        files = {
            f"chart_{index}": (photo.filename, photo.content, "image/png")
            for index, photo in enumerate(bounded_photos)
        }
        await self._post(
            "sendMediaGroup",
            data={"chat_id": chat_id, "media": json.dumps(media)},
            files=files,
        )

    async def send_message(self, *, chat_id: str, text: str) -> None:
        await self._post(
            "sendMessage",
            data={"chat_id": chat_id, "text": text[:4096]},
        )

    async def get_updates(self, *, offset: int) -> list[TelegramUpdate]:
        result = await self._post(
            "getUpdates",
            paced=False,
            data={
                "offset": str(offset),
                "timeout": "0",
                "allowed_updates": json.dumps(["message"]),
            },
        )
        return TypeAdapter(list[TelegramUpdate]).validate_python(result or [])
