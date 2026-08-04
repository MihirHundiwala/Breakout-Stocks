from time import perf_counter

from prometheus_client import Counter, Gauge, Histogram
from starlette.types import ASGIApp, Message, Receive, Scope, Send


HTTP_REQUESTS = Counter(
    "breakout_http_requests_total",
    "HTTP requests completed by the API.",
    ("method", "route", "status"),
)
HTTP_DURATION = Histogram(
    "breakout_http_request_duration_seconds",
    "Server-side HTTP request duration.",
    ("method", "route"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
HTTP_IN_PROGRESS = Gauge(
    "breakout_http_requests_in_progress",
    "HTTP requests currently being processed.",
    ("method",),
)


class PrometheusHttpMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http" or scope.get("path") == "/metrics":
            await self.app(scope, receive, send)
            return
        method = str(scope.get("method", "UNKNOWN"))
        status_code = 500
        started_at = perf_counter()

        async def capture_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        HTTP_IN_PROGRESS.labels(method=method).inc()
        try:
            await self.app(scope, receive, capture_status)
        finally:
            route = scope.get("route")
            route_template = getattr(route, "path", "unmatched")
            HTTP_IN_PROGRESS.labels(method=method).dec()
            HTTP_REQUESTS.labels(
                method=method,
                route=route_template,
                status=str(status_code),
            ).inc()
            HTTP_DURATION.labels(
                method=method,
                route=route_template,
            ).observe(perf_counter() - started_at)
