from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.routes.metrics import prometheus_metrics
from app.core.metrics import PrometheusHttpMiddleware


def test_http_metrics_use_route_templates_instead_of_ids() -> None:
    test_app = FastAPI()
    test_app.add_middleware(PrometheusHttpMiddleware)

    @test_app.get("/stocks/{stock_id}")
    def stock(stock_id: int) -> dict[str, int]:
        return {"id": stock_id}

    with TestClient(test_app) as client:
        assert client.get("/stocks/123456789").status_code == 200

    response = prometheus_metrics(
        SimpleNamespace(metrics_enabled=True, metrics_bearer_token=None),
    )
    body = response.body.decode()
    assert 'route="/stocks/{stock_id}"' in body
    assert 'route="/stocks/123456789"' not in body


def test_metrics_endpoint_requires_configured_bearer_token() -> None:
    settings = SimpleNamespace(
        metrics_enabled=True,
        metrics_bearer_token=SecretStr("synthetic-metrics-token"),
    )

    with pytest.raises(Exception) as missing:
        prometheus_metrics(settings)
    assert getattr(missing.value, "status_code", None) == 401

    response = prometheus_metrics(
        settings,
        authorization="Bearer synthetic-metrics-token",
    )
    assert response.status_code == 200
