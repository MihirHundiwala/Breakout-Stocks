from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True,
        extra="ignore",
        frozen=True,
        populate_by_name=True,
    )

    postgres_host: str = Field(validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(validation_alias="POSTGRES_PORT")
    postgres_db: str = Field(validation_alias="POSTGRES_DB")
    postgres_user: str = Field(validation_alias="POSTGRES_USER")
    postgres_password: SecretStr = Field(
        validation_alias="POSTGRES_PASSWORD"
    )
    postgres_sslmode: Literal[
        "disable", "allow", "prefer", "require", "verify-ca", "verify-full"
    ] = Field(
        default="prefer",
        validation_alias="POSTGRES_SSLMODE",
    )
    database_connect_timeout_seconds: int = Field(
        default=5,
        validation_alias="DATABASE_CONNECT_TIMEOUT_SECONDS",
    )
    database_statement_timeout_seconds: int = Field(
        default=8,
        validation_alias="DATABASE_STATEMENT_TIMEOUT_SECONDS",
    )
    database_pool_size: int = Field(
        default=5,
        ge=1,
        le=50,
        validation_alias="DATABASE_POOL_SIZE",
    )
    database_max_overflow: int = Field(
        default=5,
        ge=0,
        le=50,
        validation_alias="DATABASE_MAX_OVERFLOW",
    )
    database_pool_timeout_seconds: int = Field(
        default=10,
        ge=1,
        le=60,
        validation_alias="DATABASE_POOL_TIMEOUT_SECONDS",
    )
    admin_username: str = Field(
        default="admin",
        min_length=1,
        max_length=64,
        validation_alias="ADMIN_USERNAME",
    )
    admin_password_hash_b64: SecretStr | None = Field(
        default=None,
        validation_alias="ADMIN_PASSWORD_HASH_B64",
    )
    admin_session_ttl_seconds: int = Field(
        default=8 * 60 * 60,
        ge=5 * 60,
        le=7 * 24 * 60 * 60,
        validation_alias="ADMIN_SESSION_TTL_SECONDS",
    )
    admin_cookie_secure: bool = Field(
        default=False,
        validation_alias="ADMIN_COOKIE_SECURE",
    )
    normal_user_watchlist_limit: int = Field(
        default=20,
        ge=1,
        le=1000,
        validation_alias="NORMAL_USER_WATCHLIST_LIMIT",
    )
    application_mode: Literal["snapshot", "watchlist"] = Field(
        default="snapshot",
        validation_alias="APPLICATION_MODE",
    )
    upstox_access_token: SecretStr | None = Field(
        default=None,
        validation_alias="UPSTOX_ACCESS_TOKEN",
    )
    upstox_timeout_seconds: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        validation_alias="UPSTOX_TIMEOUT_SECONDS",
    )
    nifty_500_instrument_key: str = Field(
        default="NSE_INDEX|Nifty 500",
        min_length=1,
        max_length=128,
        validation_alias="NIFTY_500_INSTRUMENT_KEY",
    )
    worker_maximum_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        validation_alias="WORKER_MAXIMUM_ATTEMPTS",
    )
    worker_retry_base_seconds: int = Field(
        default=60,
        ge=1,
        le=3600,
        validation_alias="WORKER_RETRY_BASE_SECONDS",
    )
    worker_upstox_requests_per_second: float = Field(
        default=1.0,
        ge=0.1,
        le=1.0,
        validation_alias="WORKER_UPSTOX_REQUESTS_PER_SECOND",
    )
    telegram_requests_per_second: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        validation_alias="TELEGRAM_REQUESTS_PER_SECOND",
    )
    worker_schedule_on_startup: bool = Field(
        default=False,
        validation_alias="WORKER_SCHEDULE_ON_STARTUP",
    )
    worker_poll_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        validation_alias="WORKER_POLL_SECONDS",
    )
    worker_stale_after_seconds: int = Field(
        default=900,
        ge=60,
        le=24 * 60 * 60,
        validation_alias="WORKER_STALE_AFTER_SECONDS",
    )
    telegram_notifications_enabled: bool = Field(
        default=False,
        validation_alias="TELEGRAM_NOTIFICATIONS_ENABLED",
    )
    telegram_bot_token: SecretStr | None = Field(
        default=None,
        validation_alias="TELEGRAM_BOT_TOKEN",
    )
    telegram_bot_username: str | None = Field(
        default=None,
        min_length=1,
        max_length=32,
        validation_alias="TELEGRAM_BOT_USERNAME",
    )
    telegram_timeout_seconds: float = Field(
        default=15.0,
        ge=1.0,
        le=60.0,
        validation_alias="TELEGRAM_TIMEOUT_SECONDS",
    )
    allowed_hosts: str = Field(
        default="localhost,127.0.0.1,backend,test,testserver",
        validation_alias="ALLOWED_HOSTS",
    )
    cors_allowed_origins: str = Field(
        default="http://localhost:5173",
        validation_alias="CORS_ALLOWED_ORIGINS",
    )
    maximum_request_body_bytes: int = Field(
        default=65536,
        ge=1024,
        le=10 * 1024 * 1024,
        validation_alias="MAXIMUM_REQUEST_BODY_BYTES",
    )
    enable_api_docs: bool = Field(
        default=True,
        validation_alias="ENABLE_API_DOCS",
    )
    metrics_enabled: bool = Field(
        default=False,
        validation_alias="METRICS_ENABLED",
    )
    metrics_bearer_token: SecretStr | None = Field(
        default=None,
        validation_alias="METRICS_BEARER_TOKEN",
    )

    @property
    def allowed_host_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_hosts.split(",") if item.strip()]

    @property
    def cors_allowed_origin_list(self) -> list[str]:
        return [
            item.strip()
            for item in self.cors_allowed_origins.split(",")
            if item.strip()
        ]

    @field_validator("admin_username")
    @classmethod
    def normalize_admin_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("ADMIN_USERNAME cannot be blank.")
        return normalized

    @field_validator("upstox_access_token", mode="before")
    @classmethod
    def normalize_optional_upstox_token(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator(
        "telegram_bot_token",
        "telegram_bot_username",
        "metrics_bearer_token",
        mode="before",
    )
    @classmethod
    def normalize_optional_telegram_value(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @model_validator(mode="after")
    def validate_external_service_configuration(self) -> "Settings":
        if self.telegram_notifications_enabled and (
            self.telegram_bot_token is None
            or self.telegram_bot_username is None
        ):
            raise ValueError(
                "TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_USERNAME are required when "
                "TELEGRAM_NOTIFICATIONS_ENABLED is true."
            )
        if self.metrics_enabled and self.metrics_bearer_token is None:
            raise ValueError(
                "METRICS_BEARER_TOKEN is required when METRICS_ENABLED is true."
            )
        return self

    @field_validator("nifty_500_instrument_key")
    @classmethod
    def normalize_nifty_500_instrument_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("NIFTY_500_INSTRUMENT_KEY cannot be blank.")
        return normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()
