import pytest
from sqlalchemy import text

from app.db.health import database_is_ready
from app.db.session import engine


@pytest.mark.anyio
async def test_database_connection() -> None:
    try:
        assert await database_is_ready() is True

        async with engine.connect() as connection:
            result = await connection.execute(
                text("SHOW statement_timeout")
            )

        assert result.scalar_one() == "8s"
    finally:
        await engine.dispose()
