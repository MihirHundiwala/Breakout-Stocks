from getpass import getpass

from app.services.auth import hash_admin_password_to_base64


MINIMUM_PASSWORD_LENGTH = 12


def main() -> None:
    password = getpass("Administrator password: ")
    confirmation = getpass("Confirm administrator password: ")

    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    if len(password) < MINIMUM_PASSWORD_LENGTH:
        raise SystemExit(
            "Administrator password must contain at least "
            f"{MINIMUM_PASSWORD_LENGTH} characters."
        )

    encoded_hash = hash_admin_password_to_base64(password)
    print("Copy this complete line into the ignored .env file:")
    print(f"ADMIN_PASSWORD_HASH_B64={encoded_hash}")


if __name__ == "__main__":
    main()
