import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.config import Settings, get_settings


router = APIRouter(tags=["metrics"])


@router.get("/metrics", include_in_schema=False)
def prometheus_metrics(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    if not settings.metrics_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    configured_token = settings.metrics_bearer_token
    if configured_token is not None:
        expected = f"Bearer {configured_token.get_secret_value()}"
        if authorization is None or not secrets.compare_digest(
            authorization,
            expected,
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
