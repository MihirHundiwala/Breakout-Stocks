from app.core.config import Settings
from app.db.url import build_database_url


def test_database_url_includes_tls_without_exposing_password() -> None:
    settings = Settings(
        postgres_host="hosted.example",
        postgres_port="5432",
        postgres_db="breakout_stocks",
        postgres_user="breakout_app",
        postgres_password="database-secret",
        postgres_sslmode="require",
    )

    url = build_database_url(settings)

    assert url.query["sslmode"] == "require"
    assert "database-secret" not in str(url)
    assert "***" in str(url)
