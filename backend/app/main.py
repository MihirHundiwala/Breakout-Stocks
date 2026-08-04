from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.admin import router as admin_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.stocks import router as stocks_router
from app.api.routes.system import router as system_router
from app.api.routes.telegram import router as telegram_router
from app.api.routes.watchlist import router as watchlist_router
from app.db.session import engine
from app.core.config import get_settings
from app.core.http_security import RequestBodyLimitMiddleware, SecurityHeadersMiddleware
from app.core.metrics import PrometheusHttpMiddleware


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()

settings = get_settings()
app = FastAPI(
    title="Breakout Stocks API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url="/redoc" if settings.enable_api_docs else None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
)

app.add_middleware(
    RequestBodyLimitMiddleware,
    maximum_bytes=settings.maximum_request_body_bytes,
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)
if settings.cors_allowed_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )
if settings.metrics_enabled:
    app.add_middleware(PrometheusHttpMiddleware)

app.include_router(system_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(metrics_router)
app.include_router(stocks_router)
app.include_router(watchlist_router)
app.include_router(telegram_router)
