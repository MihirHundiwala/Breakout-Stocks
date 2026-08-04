import asyncio

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import engine


settings = get_settings()


async def database_is_ready() -> bool:
    try:
        async with asyncio.timeout(
            settings.database_connect_timeout_seconds
        ):
            async with engine.connect() as connection:
                result = await connection.execute(text("SELECT 1"))
    except (TimeoutError, SQLAlchemyError):
        return False

    return result.scalar_one() == 1
