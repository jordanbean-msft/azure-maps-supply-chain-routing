import asyncio
import hashlib
import json
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlsplit

from azure.core.exceptions import AzureError
from fastapi import APIRouter, Header, Path, Request, Response
from fastapi.responses import StreamingResponse

from template_repository.errors import ServiceError
from template_repository.models.app_config import AppConfig
from template_repository.models.auth_config import AuthConfig
from template_repository.models.disruption import Disruption
from template_repository.models.geocode_request import GeocodeRequest
from template_repository.models.geocode_result import GeocodeResult
from template_repository.models.maps_token import MapsToken
from template_repository.models.optimization_run import OptimizationRun
from template_repository.models.route_candidate import RouteCandidate
from template_repository.models.scenario import Scenario
from template_repository.runtime import Runtime
from template_repository.seed import seed_scenario
from template_repository.services.runs import TERMINAL
from template_repository.telemetry import cache_hits

Identifier = Annotated[str, Path(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")]


def _etag(value: str | None) -> str:
    if not value:
        raise ServiceError(428, "If-Match is required; retrieve the scenario ETag first.")
    if not re.fullmatch(r'"[^"\r\n]{1,200}"', value):
        raise ServiceError(412, "A single exact ETag is required.")
    return value


def create_router(runtime: Runtime) -> APIRouter:
    router = APIRouter()

    @router.get("/api/auth/config")
    async def auth_config(response: Response) -> AuthConfig:
        settings = runtime.settings
        response.headers["Cache-Control"] = "no-store"
        return AuthConfig(
            enabled=settings.auth_enabled,
            tenant_id=str(settings.entra_tenant_id) if settings.entra_tenant_id else None,
            client_id=str(settings.entra_client_id) if settings.entra_client_id else None,
            scope=settings.entra_api_scope,
        )

    @router.get("/health")
    @router.get("/health/live")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/health/ready")
    async def ready(response: Response) -> dict[str, str]:
        try:
            runtime.require_ready()
            await runtime.repository.ready()
        except ServiceError:
            response.status_code = 503
            return {"status": "not_ready", "reason": "live_services_not_initialized"}
        return {"status": "ok", "mode": runtime.settings.app_mode}

    @router.get("/api/config")
    async def config() -> AppConfig:
        return AppConfig(
            mode=runtime.settings.app_mode,
            routing_source="simulated" if runtime.settings.app_mode == "demo" else "azure_maps",
            routing_available=runtime.initialized,
            maps_available=runtime.initialized
            and runtime.browser_credential is not None
            and bool(runtime.settings.maps_allowed_origins),
            persistence="memory" if runtime.settings.app_mode == "demo" else "cosmos",
        )

    @router.get("/api/maps/token")
    async def maps_token(request: Request, response: Response) -> MapsToken:
        runtime.require_ready()
        response.headers["Cache-Control"] = "no-store"
        if runtime.browser_credential is None:
            raise ServiceError(
                503, "A separate render-only Maps browser identity is not configured."
            )
        origin = request.headers.get("origin")
        if origin is None and request.headers.get("sec-fetch-site") == "same-origin":
            try:
                referer = urlsplit(request.headers.get("referer", ""))
                origin = f"{referer.scheme}://{referer.netloc}"
            except ValueError:
                origin = None
        if origin not in runtime.settings.maps_allowed_origins:
            raise ServiceError(403, "Maps token origin is not allowed.")
        try:
            token = await runtime.browser_credential.get_token(
                "https://atlas.microsoft.com/.default"
            )
        except AzureError as error:
            raise ServiceError(503, "Maps browser identity unavailable.") from error
        return MapsToken(
            token=token.token,
            client_id=runtime.settings.azure_maps_client_id or "",
            expires_on=datetime.fromtimestamp(token.expires_on, UTC),
        )

    @router.get("/api/scenarios")
    async def scenarios() -> list[Scenario]:
        runtime.require_ready()
        # Anonymous scenario IDs are bearer capabilities, never enumerate user input.
        return []

    @router.post("/api/scenarios", status_code=201)
    async def create(scenario: Scenario, response: Response) -> Scenario:
        runtime.require_ready()
        document = await runtime.scenarios.create(scenario)
        response.headers.update(
            {"ETag": document.etag, "Location": f"/api/scenarios/{scenario.id}"}
        )
        return scenario

    @router.post("/api/scenarios/seed", status_code=201)
    async def seed(response: Response) -> Scenario:
        return await create(seed_scenario(), response)

    @router.get("/api/scenarios/{scenario_id}")
    async def get(scenario_id: Identifier, response: Response) -> Scenario:
        runtime.require_ready()
        scenario, document = await runtime.scenarios.get(scenario_id)
        response.headers["ETag"] = document.etag
        return scenario

    @router.put("/api/scenarios/{scenario_id}")
    async def update(
        scenario_id: Identifier,
        scenario: Scenario,
        response: Response,
        if_match: Annotated[str | None, Header()] = None,
    ) -> Scenario:
        runtime.require_ready()
        if scenario_id != scenario.id:
            raise ServiceError(422, "Path and scenario identifier must match.")
        document = await runtime.scenarios.update(scenario, _etag(if_match))
        response.headers["ETag"] = document.etag
        return scenario

    @router.delete("/api/scenarios/{scenario_id}", status_code=204)
    async def delete(
        scenario_id: Identifier, if_match: Annotated[str | None, Header()] = None
    ) -> Response:
        runtime.require_ready()
        await runtime.repository.delete(scenario_id, scenario_id, _etag(if_match))
        return Response(status_code=204)

    @router.post("/api/scenarios/{scenario_id}/locations:geocode")
    async def geocode(scenario_id: Identifier, query: GeocodeRequest) -> list[GeocodeResult]:
        runtime.require_ready()
        await runtime.scenarios.get(scenario_id)
        key = "geocode-" + hashlib.sha256(query.address.strip().lower().encode()).hexdigest()
        try:
            cached = await runtime.repository.get(scenario_id, key)
            cache_hits.add(1, {"kind": "geocode"})
            return [GeocodeResult.model_validate(value) for value in cached.body["results"]]
        except ServiceError as error:
            if error.status != 404:
                raise
        results = await runtime.routing.geocode(query.address)
        results = [x for x in results if 24 <= x.latitude <= 50 and -125 <= x.longitude <= -66]
        try:
            await runtime.repository.create(
                {
                    "id": key,
                    "scenario_id": scenario_id,
                    "kind": "geocode",
                    "ttl": runtime.settings.snapshot_ttl_seconds,
                    "results": [x.model_dump(mode="json") for x in results],
                }
            )
        except ServiceError as error:
            if error.status != 409:
                raise
        return results

    @router.post("/api/scenarios/{scenario_id}/optimize", status_code=202)
    async def optimize(
        scenario_id: Identifier,
        response: Response,
        idempotency_key: Annotated[str | None, Header()] = None,
    ) -> OptimizationRun:
        runtime.require_ready()
        if idempotency_key is not None and not re.fullmatch(
            r"[A-Za-z0-9_-]{1,100}", idempotency_key
        ):
            raise ServiceError(
                422, "Idempotency-Key must be 1..100 alphanumeric, dash or underscore characters."
            )
        scenario, _ = await runtime.scenarios.get(scenario_id)
        run = await runtime.runs.submit(scenario, idempotency_key)
        response.headers["Location"] = f"/api/scenarios/{scenario_id}/runs/{run.id}"
        return run

    @router.get("/api/scenarios/{scenario_id}/runs/{run_id}")
    async def run_detail(scenario_id: Identifier, run_id: Identifier) -> OptimizationRun:
        runtime.require_ready()
        await runtime.scenarios.get(scenario_id)
        return (await runtime.runs.get(scenario_id, run_id))[0]

    @router.get("/api/scenarios/{scenario_id}/runs/{run_id}/events")
    async def events(
        scenario_id: Identifier,
        run_id: Identifier,
        request: Request,
        last_event_id: Annotated[str | None, Header()] = None,
    ) -> StreamingResponse:
        await run_detail(scenario_id, run_id)
        if last_event_id is not None and (not last_event_id.isdigit() or len(last_event_id) > 9):
            raise ServiceError(422, "Last-Event-ID must be a nonnegative sequence number.")
        sequence = int(last_event_id or 0)

        async def stream() -> AsyncIterator[str]:
            nonlocal sequence
            while not await request.is_disconnected():
                run, document = await runtime.runs.get(scenario_id, run_id)
                for event in document.body["events"]:
                    if event["sequence"] > sequence:
                        sequence = event["sequence"]
                        from_json = json.dumps(event)
                        yield f"id: {sequence}\nevent: progress\ndata: {from_json}\n\n"
                if run.status in TERMINAL:
                    return
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @router.get("/api/scenarios/{scenario_id}/routes/{route_id}")
    async def route_detail(scenario_id: Identifier, route_id: Identifier) -> RouteCandidate:
        runtime.require_ready()
        await runtime.scenarios.get(scenario_id)
        latest = await runtime.repository.get(scenario_id, "latest")
        run, _ = await runtime.runs.get(scenario_id, latest.body["run_id"])
        for route in run.routes:
            if route.id == route_id:
                return route
        raise ServiceError(404, "Route not found in the latest snapshot.")

    @router.post("/api/scenarios/{scenario_id}/disruptions", status_code=201)
    async def add_disruption(
        scenario_id: Identifier,
        disruption: Disruption,
        response: Response,
        if_match: Annotated[str | None, Header()] = None,
    ) -> Scenario:
        runtime.require_ready()
        scenario, _ = await runtime.scenarios.get(scenario_id)
        if any(value.id == disruption.id for value in scenario.disruptions):
            raise ServiceError(409, "Disruption identifier already exists.")
        value = scenario.model_dump(mode="json")
        value["disruptions"].append(disruption.model_dump(mode="json"))
        scenario = runtime.scenarios.revalidate(value)
        return await update(scenario_id, scenario, response, if_match)

    @router.delete("/api/scenarios/{scenario_id}/disruptions/{disruption_id}")
    async def delete_disruption(
        scenario_id: Identifier,
        disruption_id: Identifier,
        response: Response,
        if_match: Annotated[str | None, Header()] = None,
    ) -> Scenario:
        runtime.require_ready()
        scenario, _ = await runtime.scenarios.get(scenario_id)
        if not any(value.id == disruption_id for value in scenario.disruptions):
            raise ServiceError(404, "Disruption not found.")
        scenario.disruptions = [
            value for value in scenario.disruptions if value.id != disruption_id
        ]
        return await update(scenario_id, scenario, response, if_match)

    return router
