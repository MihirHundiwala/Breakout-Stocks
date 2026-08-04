import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import async_session_factory, engine
from app.fixtures import seed_stock_fixtures
from app.models import AppUser, UserRole


async def run() -> None:
    try:
        async with async_session_factory() as session:
            async with session.begin():
                admin = await session.scalar(
                    select(AppUser).where(AppUser.role == UserRole.ADMIN)
                )
                if admin is None:
                    admin = AppUser(
                        username=get_settings().admin_username,
                        role=UserRole.ADMIN,
                        password_hash=None,
                    )
                    session.add(admin)
                    await session.flush()
                summary = await seed_stock_fixtures(
                    session,
                    owner_user_id=admin.id,
                )
    finally:
        await engine.dispose()

    print(
        "Fixture seed complete: "
        f"{summary.companies_created} companies, "
        f"{summary.instruments_created} instruments, "
        f"{summary.snapshots_created} snapshots, "
        f"{summary.trackings_created} tracking rows, "
        f"{summary.memberships_created} admin memberships created."
    )


if __name__ == "__main__":
    asyncio.run(run())
