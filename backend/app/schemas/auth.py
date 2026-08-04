from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, SecretStr


from app.models import UserRole


class AuthLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=1024)


class AuthSignupRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=1024)


class AuthSessionResponse(BaseModel):
    authenticated: Literal[True] = True
    username: str
    role: UserRole
    watchlist_limit: int | None
    expires_at: datetime


AdminLoginRequest = AuthLoginRequest
AdminSessionResponse = AuthSessionResponse
