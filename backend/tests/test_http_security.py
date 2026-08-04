import pytest
from httpx2 import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.anyio
async def test_security_headers_are_present() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.anyio
async def test_oversized_request_is_rejected_before_route_handling() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/auth/login",
            content=b"x" * 65537,
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 413
    assert response.json() == {"detail": "REQUEST_BODY_TOO_LARGE"}
