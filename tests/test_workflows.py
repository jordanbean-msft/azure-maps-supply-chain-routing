import asyncio
import json
import time
from unittest.mock import AsyncMock

import httpx
import pytest
from azure.core.credentials import AccessToken

from template_repository.app import create_app
from template_repository.config import Settings
from template_repository.errors import ServiceError
from template_repository.models.scenario import Scenario
from template_repository.persistence.memory import MemoryRepository
from template_repository.routing.simulated import SimulatedRouting
from template_repository.seed import seed_scenario
from template_repository.services.runs import RunService


async def completed(client: httpx.AsyncClient, path: str) -> dict:
    for _ in range(100):
        result = await client.get(path)
        assert result.status_code == 200
        run = result.json()
        if run["status"] in {"completed", "failed", "infeasible"}:
            return run
        await asyncio.sleep(0.01)
    pytest.fail("Run did not reach a terminal state")


async def test_seed_crud_optimize_disruption_events_and_etags(client: httpx.AsyncClient) -> None:
    seeded = await client.post("/api/scenarios/seed")
    assert seeded.status_code == 201
    scenario = seeded.json()
    path = seeded.headers["location"]
    etag = seeded.headers["etag"]
    assert (await client.get("/api/scenarios")).json() == []
    assert (await client.post("/api/scenarios", json=scenario)).status_code == 409
    assert (await client.get(path)).headers["etag"] == etag
    assert (await client.put(path, json=scenario)).status_code == 428
    assert (await client.put(path, json=scenario, headers={"If-Match": '"old"'})).status_code == 412
    scenario["name"] = "Edited network"
    edited = await client.put(path, json=scenario, headers={"If-Match": etag})
    etag = edited.headers["etag"]
    geocoded = await client.post(path + "/locations:geocode", json={"address": "Seattle"})
    assert geocoded.json()[0]["latitude"] == 47.6062
    assert (
        await client.post(path + "/locations:geocode", json={"address": "Seattle"})
    ).json() == geocoded.json()
    assert (
        await client.post(path + "/locations:geocode", json={"address": "Unknown"})
    ).json() == []
    submitted = await client.post(path + "/optimize", headers={"Idempotency-Key": "original"})
    assert submitted.status_code == 202
    assert submitted.json()["status"] == "queued"
    run_url = submitted.headers["location"]
    run = await completed(client, run_url)
    assert run["status"] == "completed", run
    assert sum(value["quantity"] for value in run["allocations"]) == 80
    assert run["total_cost"] == sum(value["total_cost"] for value in run["allocations"])
    assert all(value["source"] == "simulated" for value in run["routes"])
    repeated = await client.post(path + "/optimize", headers={"Idempotency-Key": "original"})
    assert repeated.json()["id"] == run["id"]
    route = run["allocations"][0]["route_id"]
    assert (await client.get(path + "/routes/" + route)).json()["id"] == route
    events = await client.get(run_url + "/events")
    assert events.headers["content-type"].startswith("text/event-stream")
    data = [json.loads(line[6:]) for line in events.text.splitlines() if line.startswith("data: ")]
    assert [item["sequence"] for item in data] == [1, 2, 3, 4]
    assert data[-1]["status"] == "completed"
    replay = await client.get(run_url + "/events", headers={"Last-Event-ID": "3"})
    assert "id: 4" in replay.text and "id: 3" not in replay.text
    assert (
        await client.get(run_url + "/events", headers={"Last-Event-ID": "no"})
    ).status_code == 422
    # Optimization activity does not mutate the scenario ETag.
    disruption = {
        "id": "closure",
        "name": "Close selected road",
        "kind": "road_closure",
        "route_id": route,
    }
    changed = await client.post(path + "/disruptions", json=disruption, headers={"If-Match": etag})
    assert changed.status_code == 201, changed.text
    new_etag = changed.headers["etag"]
    assert (
        await client.post(path + "/disruptions", json=disruption, headers={"If-Match": new_etag})
    ).status_code == 409
    rerun = await client.post(path + "/optimize")
    rerun_result = await completed(client, rerun.headers["location"])
    assert rerun_result["status"] == "completed"
    assert route not in {value["route_id"] for value in rerun_result["allocations"]}
    removed = await client.delete(path + "/disruptions/closure", headers={"If-Match": new_etag})
    assert removed.status_code == 200 and removed.json()["disruptions"] == []
    assert (await client.delete(path, headers={"If-Match": etag})).status_code == 412
    assert (
        await client.delete(path, headers={"If-Match": removed.headers["etag"]})
    ).status_code == 204
    assert (await client.get(path)).status_code == 404
    assert (await client.get(run_url)).status_code == 404


@pytest.mark.parametrize(
    "disruption",
    [
        {"kind": "road_closure"},
        {"kind": "road_closure", "route_id": "missing"},
        {"kind": "facility_delay", "location_id": "missing", "delay_minutes": 10},
        {"kind": "facility_delay", "location_id": "houston", "delay_minutes": 0},
        {"kind": "weather", "severity": 1.1},
        {"kind": "weather", "severity": 0.5, "delay_minutes": 1},
        {"kind": "fuel_price", "fuel_price_per_liter": 5, "location_id": "houston"},
    ],
)
async def test_invalid_disruption_is_problem_details(
    client: httpx.AsyncClient, disruption: dict
) -> None:
    seed = await client.post("/api/scenarios/seed")
    response = await client.post(
        seed.headers["location"] + "/disruptions",
        headers={"If-Match": seed.headers["etag"]},
        json={"id": "d", "name": "Test", **disruption},
    )
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


async def test_request_validation_and_unknown_entities(client: httpx.AsyncClient) -> None:
    seed = await client.post("/api/scenarios/seed")
    path = seed.headers["location"]
    scenario = seed.json()
    mismatch = dict(scenario, id="different")
    assert (
        await client.put(path, json=mismatch, headers={"If-Match": seed.headers["etag"]})
    ).status_code == 422
    assert (
        await client.post(path + "/optimize", headers={"Idempotency-Key": "!"})
    ).status_code == 422
    assert (await client.get(path + "/runs/missing")).status_code == 404
    assert (await client.get(path + "/routes/missing")).status_code == 404
    assert (
        await client.delete(
            path + "/disruptions/missing", headers={"If-Match": seed.headers["etag"]}
        )
    ).status_code == 404
    empty = dict(scenario, id="empty", locations=[])
    assert (await client.post("/api/scenarios", json=empty)).status_code == 201
    assert (await client.post("/api/scenarios/empty/optimize")).status_code == 422
    bad = dict(scenario, id="invalid", locations=[dict(scenario["locations"][0], latitude=0)])
    assert (await client.post("/api/scenarios", json=bad)).status_code == 422
    bad["id"] = "latest"
    assert (await client.post("/api/scenarios", json=bad)).status_code == 422


async def test_size_origin_and_rate_budgets() -> None:
    app = create_app(
        Settings(
            _env_file=None,
            requests_per_minute=4,
            max_request_bytes=1024,
            expensive_requests_per_minute=1,
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.post("/api/scenarios", content="a" * 1025)).status_code == 413
        assert (await client.post("/api/scenarios/seed")).status_code == 429
        assert (
            await client.put("/api/scenarios/test", headers={"Origin": "https://evil.example"})
        ).status_code == 403
        response = await client.get("/missing", headers={"X-Request-ID": "correlation"})
        assert response.headers["x-request-id"] == "correlation"
        assert response.json()["status"] == 404
        assert (await client.get("/api/config")).status_code == 429
        assert (await client.get("/health")).status_code == 200


async def test_injected_live_workflow_and_origin_scoped_token() -> None:
    settings = Settings(
        _env_file=None,
        app_mode="live",
        azure_maps_client_id="maps-account",
        maps_allowed_origins=["https://demo.example"],
    )
    app = create_app(settings, repository=MemoryRepository(), routing=SimulatedRouting())
    credential = AsyncMock()
    credential.get_token.return_value = AccessToken("render-only-token", int(time.time()) + 3600)
    app.state.runtime.browser_credential = credential
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://demo.example"
        ) as client,
    ):
        assert (await client.get("/health/ready")).status_code == 200
        assert (await client.get("/api/maps/token")).status_code == 403
        result = await client.get("/api/maps/token", headers={"Origin": "https://demo.example"})
        assert result.json()["client_id"] == "maps-account"
        assert result.headers["cache-control"] == "no-store"
        assert (await client.get("/api/config")).json()["maps_available"] is True
        browser_request = await client.get(
            "/api/maps/token",
            headers={"Sec-Fetch-Site": "same-origin", "Referer": "https://demo.example/planning"},
        )
        assert browser_request.status_code == 200
        rejected = await client.get(
            "/api/maps/token",
            headers={"Sec-Fetch-Site": "cross-site", "Referer": "https://demo.example/planning"},
        )
        assert rejected.status_code == 403


async def test_run_snapshot_deadline_failure_and_shutdown() -> None:
    repository = MemoryRepository()
    settings = Settings(_env_file=None, max_concurrent_runs=1)
    routing = AsyncMock()
    blocker = asyncio.Event()

    async def blocked(scenario: Scenario) -> tuple[list, list]:
        await blocker.wait()
        return [], []

    routing.routes.side_effect = blocked
    service = RunService(repository, routing, settings)
    scenario = seed_scenario()
    run = await service.submit(scenario, "same")
    assert (await service.submit(scenario, "same")).id == run.id
    with pytest.raises(ServiceError, match="concurrency"):
        await service.submit(scenario)
    document = await repository.get(scenario.id, run.id)
    assert document.body["snapshot"] == scenario.model_dump(mode="json")
    await asyncio.sleep(0)
    await service.close()
    terminal, _ = await service.get(scenario.id, run.id)
    assert terminal.status == "failed"
    # Simulate replica death by expiring a persisted nonterminal run lease.
    document = await repository.get(scenario.id, run.id)
    document.body["run"]["status"] = "queued"
    document.body["deadline"] = time.time() - 1
    await repository.replace(document.body, document.etag)
    recovered, document = await service.get(scenario.id, run.id)
    assert recovered.status == "failed" and recovered.stage == "expired"
    assert document.body["events"][-1]["status"] == "failed"


async def test_upstream_failure_is_failed_not_infeasible(client: httpx.AsyncClient) -> None:
    runtime = client.application.state.runtime
    runtime.runs.routing = AsyncMock()
    runtime.runs.routing.routes.side_effect = ServiceError(503, "Maps throttled.")
    seed = await client.post("/api/scenarios/seed")
    submitted = await client.post(seed.headers["location"] + "/optimize")
    run = await completed(client, submitted.headers["location"])
    assert run["status"] == "failed" and run["error"] == "Maps throttled."
    assert run["allocations"] == []


async def test_api_infeasible_retains_candidates_but_no_successful_allocations(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/api/scenarios/seed")
    scenario = response.json()
    for location in scenario["locations"]:
        if location["kind"] == "factory":
            location["quantity"] = 0
    path = response.headers["location"]
    assert (
        await client.put(path, json=scenario, headers={"If-Match": response.headers["etag"]})
    ).status_code == 200
    submitted = await client.post(path + "/optimize")
    result = await completed(client, submitted.headers["location"])
    assert result["status"] == "infeasible"
    assert result["allocations"] == [] and result["total_cost"] == 0
    assert result["routes"]
