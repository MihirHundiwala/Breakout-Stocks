from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from app.db.health import database_is_ready


router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    database: Literal["ok", "unavailable"]


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Check API liveness",
)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Check API readiness",
)
async def readiness_check(
    response: Response,
    database_ready: Annotated[bool, Depends(database_is_ready)],
) -> ReadinessResponse:
    if not database_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="not_ready",
            database="unavailable",
        )

    return ReadinessResponse(status="ready", database="ok")
