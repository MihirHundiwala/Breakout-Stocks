import os

import uvicorn


def application_port() -> int:
    raw_port = os.getenv("PORT", "8000")
    try:
        port = int(raw_port)
    except ValueError as error:
        raise RuntimeError("PORT must be an integer.") from error
    if not 1 <= port <= 65535:
        raise RuntimeError("PORT must be between 1 and 65535.")
    return port


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=application_port(),
    )


if __name__ == "__main__":
    main()
