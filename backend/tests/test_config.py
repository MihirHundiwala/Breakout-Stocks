import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_validate_and_mask_database_configuration() -> None:
    settings = Settings(
        postgres_host="database",
        postgres_port="5432",
        postgres_db="breakout_stocks",
        postgres_user="breakout_app",
        postgres_password="test-password",
        upstox_access_token=None,
    )

    assert settings.postgres_port == 5432
    assert settings.postgres_sslmode == "prefer"
    assert settings.database_connect_timeout_seconds == 5
    assert settings.database_statement_timeout_seconds == 8
    assert settings.admin_username == "admin"
    assert settings.admin_session_ttl_seconds == 8 * 60 * 60
    assert settings.admin_cookie_secure is False
    assert settings.normal_user_watchlist_limit == 20
    assert settings.upstox_access_token is None
    assert settings.upstox_timeout_seconds == 10.0
    assert settings.worker_upstox_requests_per_second == 1.0
    assert settings.worker_schedule_on_startup is False
    assert settings.nifty_500_instrument_key == "NSE_INDEX|Nifty 500"
    assert "test-password" not in repr(settings)


def test_settings_mask_and_normalize_upstox_token() -> None:
    settings = Settings(
        postgres_host="database",
        postgres_port="5432",
        postgres_db="breakout_stocks",
        postgres_user="breakout_app",
        postgres_password="test-password",
        upstox_access_token=" provider-secret ",
    )

    assert settings.upstox_access_token is not None
    assert settings.upstox_access_token.get_secret_value() == "provider-secret"
    assert "provider-secret" not in repr(settings)


def test_settings_accept_hosted_database_tls_mode() -> None:
    settings = Settings(
        postgres_host="hosted.example",
        postgres_port="5432",
        postgres_db="breakout_stocks",
        postgres_user="breakout_app",
        postgres_password="test-password",
        postgres_sslmode="require",
    )

    assert settings.postgres_sslmode == "require"


def test_settings_normalize_nifty_500_instrument_key() -> None:
    settings = Settings(
        postgres_host="database",
        postgres_port="5432",
        postgres_db="breakout_stocks",
        postgres_user="breakout_app",
        postgres_password="test-password",
        nifty_500_instrument_key=" NSE_INDEX|Nifty 500 ",
    )

    assert settings.nifty_500_instrument_key == "NSE_INDEX|Nifty 500"


def test_worker_request_rate_rejects_unsafe_sustained_value() -> None:
    with pytest.raises(ValidationError):
        Settings(
            postgres_host="database",
            postgres_port="5432",
            postgres_db="breakout_stocks",
            postgres_user="breakout_app",
            postgres_password="test-password",
            worker_upstox_requests_per_second=1.1,
        )


def test_enabled_metrics_require_a_bearer_token() -> None:
    with pytest.raises(ValidationError, match="METRICS_BEARER_TOKEN"):
        Settings(
            postgres_host="database",
            postgres_port="5432",
            postgres_db="breakout_stocks",
            postgres_user="breakout_app",
            postgres_password="test-password",
            metrics_enabled=True,
        )

    settings = Settings(
        postgres_host="database",
        postgres_port="5432",
        postgres_db="breakout_stocks",
        postgres_user="breakout_app",
        postgres_password="test-password",
        metrics_enabled=True,
        metrics_bearer_token=" synthetic-metrics-secret ",
    )
    assert settings.metrics_bearer_token is not None
    assert (
        settings.metrics_bearer_token.get_secret_value()
        == "synthetic-metrics-secret"
    )
