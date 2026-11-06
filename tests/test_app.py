import importlib
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from template_repository.app import app, create_app
from template_repository.config import Settings


class TestHealth:
    def test_health_returns_ok(self) -> None:
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("path", ["/health", "/health/live", "/health/ready"])
async def test_demo_health(path: str) -> None:
    application = create_app(Settings(_env_file=None, app_mode="demo"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.get(path)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_no_credentials_demo_is_explicitly_simulated() -> None:
    application = create_app(Settings(_env_file=None, app_mode="demo"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://test"
    ) as client:
        config = (await client.get("/api/config")).json()
        token = await client.get("/api/maps/token")
    assert config["routing_source"] == "simulated"
    assert config["routing_available"] is True
    assert config["maps_available"] is False
    assert token.status_code == 503


async def test_uninitialized_live_services_do_not_report_success() -> None:
    application = create_app(Settings(_env_file=None, app_mode="live"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://test"
    ) as client:
        readiness = await client.get("/health/ready")
        config = (await client.get("/api/config")).json()
    assert readiness.status_code == 503
    assert config["routing_source"] == "azure_maps"
    assert config["routing_available"] is False
    assert config["maps_available"] is False


def test_import_does_not_configure_logging_or_create_directories() -> None:
    module = importlib.import_module("template_repository.app")
    with patch("logging.config.dictConfig") as configure, patch("pathlib.Path.mkdir") as mkdir:
        importlib.reload(module)
    configure.assert_not_called()
    mkdir.assert_not_called()
