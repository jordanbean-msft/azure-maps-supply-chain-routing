import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from azure.core.credentials import AccessToken
from azure.core.exceptions import AzureError

from template_repository.app import create_app
from template_repository.config import Settings
from template_repository.errors import ServiceError
from template_repository.refresh import _refresh_one, refresh
from template_repository.routing.simulated import SimulatedRouting
from template_repository.runtime import Runtime
from template_repository.seed import seed_scenario
from template_repository.telemetry import configure_telemetry


async def test_refresh_opt_in_bound_actual_recomputation_and_expired_scenarios() -> None:
    settings = Settings(_env_file=None, refresh_enabled=True, refresh_max_scenarios=2)
    runtime = Runtime(settings)
    routing = AsyncMock(wraps=SimulatedRouting())
    runtime.runs.routing = routing
    expected_active = {}
    for _ in range(3):
        scenario = seed_scenario()
        await runtime.scenarios.create(scenario)
        await runtime.scenarios.mark_active(scenario)
        active = await runtime.repository.get(scenario.id, "active")
        expected_active[scenario.id] = active.body["active_at"]

    def build(configuration: Settings) -> Runtime:
        assert configuration.maps_cache_seconds == 0
        return runtime

    with patch("template_repository.refresh.Runtime", side_effect=build):
        assert await refresh(settings) == 2
    assert routing.routes.await_count == 2
    active = await runtime.repository.active_scenarios(5, time.time() - 3600)
    for document in active:
        assert document.body["active_at"] == expected_active[document.body["scenario_id"]]
    with patch("template_repository.refresh.Runtime") as factory:
        assert await refresh(Settings(_env_file=None)) == 0
        factory.assert_not_called()


async def test_failed_refresh_records_failed_run() -> None:
    runtime = Runtime(Settings(_env_file=None))
    runtime.runs.routing = AsyncMock()
    runtime.runs.routing.routes.side_effect = ServiceError(503, "Upstream unavailable")
    scenario = seed_scenario()
    await runtime.scenarios.create(scenario)
    with pytest.raises(ServiceError, match="Upstream"):
        await _refresh_one(runtime, scenario)
    await runtime.close()


async def test_missing_live_settings_remains_unready_with_lifespan() -> None:
    application = create_app(Settings(_env_file=None, app_mode="live"))
    async with (
        application.router.lifespan_context(application),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application), base_url="http://test"
        ) as client,
    ):
        assert (await client.get("/health")).status_code == 200
        assert (await client.get("/health/ready")).status_code == 503
        assert (await client.post("/api/scenarios/seed")).status_code == 503
        token = await client.get("/api/maps/token")
        assert token.status_code == 503 and token.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "error",
    [
        ServiceError(503, "startup unavailable"),
        AzureError("startup unavailable"),
        TimeoutError("startup unavailable"),
    ],
)
async def test_configured_live_startup_failure_aborts_lifespan_and_closes_resources(
    error: Exception,
) -> None:
    application = create_app(
        Settings(
            _env_file=None,
            app_mode="live",
            azure_maps_client_id="maps-account",
            cosmos_endpoint="https://test.documents.azure.com",
        )
    )
    runtime = application.state.runtime
    with (
        patch.object(runtime, "start", side_effect=error) as start,
        patch.object(runtime, "close", wraps=runtime.close) as close,
        pytest.raises(type(error), match="startup unavailable") as caught,
    ):
        async with application.router.lifespan_context(application):
            pytest.fail("A failed configured startup must not begin serving requests.")
    assert caught.value is error
    start.assert_awaited_once()
    close.assert_awaited_once()
    assert not runtime.initialized


async def test_live_initialization_managed_identity_clients_and_resource_cleanup() -> None:
    settings = Settings(
        _env_file=None,
        app_mode="live",
        azure_client_id="backend-mi",
        maps_browser_client_id="browser-mi",
        azure_maps_client_id="maps-account",
        cosmos_endpoint="https://test.documents.azure.com",
    )
    identity = AsyncMock()
    identity.get_token.return_value = AccessToken("private", int(time.time()) + 3600)
    browser = AsyncMock()
    cosmos = MagicMock()
    cosmos.__aenter__ = AsyncMock(return_value=cosmos)
    cosmos.__aexit__ = AsyncMock()
    container = MagicMock()
    container.read = AsyncMock(
        return_value={"partitionKey": {"paths": ["/scenario_id"]}, "defaultTtl": -1}
    )
    cosmos.get_database_client.return_value.get_container_client.return_value = container
    with (
        patch(
            "template_repository.runtime.ManagedIdentityCredential", side_effect=[identity, browser]
        ) as credentials,
        patch("template_repository.runtime.CosmosClient", return_value=cosmos),
    ):
        runtime = Runtime(settings)
        await runtime.start()
        assert runtime.initialized
        assert credentials.call_args_list[0].kwargs == {"client_id": "backend-mi"}
        assert credentials.call_args_list[1].kwargs == {"client_id": "browser-mi"}
        identity.get_token.assert_awaited_once_with("https://atlas.microsoft.com/.default")
        await runtime.close()
    assert not runtime.initialized
    identity.close.assert_awaited_once()
    browser.close.assert_awaited_once()
    cosmos.__aexit__.assert_awaited_once()


def test_telemetry_requires_explicit_opt_in() -> None:
    with patch("template_repository.telemetry.configure_azure_monitor") as configure:
        configure_telemetry(
            Settings(_env_file=None, applicationinsights_connection_string="configured")
        )
        configure.assert_not_called()
        configure_telemetry(
            Settings(
                _env_file=None,
                telemetry_enabled=True,
                applicationinsights_connection_string="configured",
            )
        )
        assert configure.call_args.kwargs["connection_string"] == "configured"
