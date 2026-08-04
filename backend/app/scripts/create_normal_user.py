import argparse
import asyncio
from getpass import getpass

from app.core.config import get_settings
from app.db.session import async_session_factory, engine
from app.services.auth import (
    InvalidPasswordError,
    UsernameUnavailableError,
    create_normal_user,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a normal Breakout Stocks user."
    )
    parser.add_argument("username", help="Lowercase login username.")
    return parser.parse_args()


async def run(username: str, password: str) -> int:
    settings = get_settings()
    try:
        async with async_session_factory() as session:
            user = await create_normal_user(
                session,
                username,
                password,
                reserved_username=settings.admin_username,
            )
    except UsernameUnavailableError:
        print("USER_CREATE_FAILED code=USERNAME_UNAVAILABLE")
        return 1
    except InvalidPasswordError:
        print("USER_CREATE_FAILED code=PASSWORD_TOO_SHORT")
        return 1
    finally:
        await engine.dispose()
    print(f"USER_CREATED username={user.username}")
    return 0


def main() -> int:
    args = parse_args()
    password = getpass("User password: ")
    confirmation = getpass("Confirm user password: ")
    if password != confirmation:
        print("USER_CREATE_FAILED code=PASSWORDS_DO_NOT_MATCH")
        return 1
    return asyncio.run(run(args.username, password))


if __name__ == "__main__":
    raise SystemExit(main())
