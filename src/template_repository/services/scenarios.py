import time
from typing import Any

from pydantic import ValidationError

from template_repository.config import Settings
from template_repository.errors import ServiceError
from template_repository.models.scenario import Scenario
from template_repository.persistence.repository import Document, Repository
from template_repository.routing.identifiers import route_id


class ScenarioService:
    def __init__(self, repository: Repository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    @staticmethod
    def validate(scenario: Scenario) -> None:
        if scenario.id in {"latest", "active"} or scenario.id.startswith(
            ("run-", "maps-", "geocode-")
        ):
            raise ServiceError(422, "Scenario identifier uses a reserved namespace.")
        # Restrict the public demo to the contiguous-US bounding box. This is a
        # transaction/cross-ocean guard, not a country-boundary determination.
        if any(
            not (24 <= x.latitude <= 50 and -125 <= x.longitude <= -66) for x in scenario.locations
        ):
            raise ServiceError(
                422, "Demo locations must be within latitude 24..50, longitude -125..-66."
            )
        expected = {
            route_id(supplier.id, factory.id, index)
            for supplier in scenario.locations
            if supplier.kind == "supplier"
            for factory in scenario.locations
            if factory.kind == "factory"
            for index in range(2)
        }
        if any(d.route_id and d.route_id not in expected for d in scenario.disruptions):
            raise ServiceError(422, "Disruption route does not belong to a current scenario lane.")

    async def validate_routes(self, scenario: Scenario) -> None:
        targeted = {d.route_id for d in scenario.disruptions if d.route_id}
        if not targeted:
            return
        try:
            latest = await self.repository.get(scenario.id, "latest")
            run = await self.repository.get(scenario.id, latest.body["run_id"])
        except ServiceError as error:
            if error.status == 404:
                raise ServiceError(
                    422, "Route disruptions require an existing route snapshot."
                ) from error
            raise
        routes = {route["id"] for route in run.body["run"]["routes"]}
        # Keep closed candidates in the snapshot separately for subsequent edits.
        routes.update(run.body.get("candidate_ids", []))
        if not targeted.issubset(routes):
            raise ServiceError(422, "Disruption target is not a known route snapshot.")

    def envelope(self, scenario: Scenario, *, active_at: float = 0) -> dict[str, Any]:
        return {
            "id": scenario.id,
            "scenario_id": scenario.id,
            "kind": "scenario",
            "ttl": self.settings.scenario_ttl_seconds,
            "active_at": active_at,
            "scenario": scenario.model_dump(mode="json"),
        }

    async def get(self, identifier: str) -> tuple[Scenario, Document]:
        document = await self.repository.get(identifier, identifier)
        return Scenario.model_validate(document.body["scenario"]), document

    async def create(self, scenario: Scenario) -> Document:
        self.validate(scenario)
        await self.validate_routes(scenario)
        return await self.repository.create(self.envelope(scenario))

    async def update(self, scenario: Scenario, etag: str) -> Document:
        self.validate(scenario)
        await self.validate_routes(scenario)
        _, current = await self.get(scenario.id)
        return await self.repository.replace(
            self.envelope(scenario, active_at=current.body.get("active_at", 0)), etag
        )

    async def mark_active(self, scenario: Scenario) -> None:
        body = {
            "id": "active",
            "scenario_id": scenario.id,
            "kind": "active",
            "ttl": self.settings.scenario_ttl_seconds,
            "active_at": time.time(),
        }
        try:
            current = await self.repository.get(scenario.id, "active")
            await self.repository.replace(body, current.etag)
        except ServiceError as error:
            if error.status == 404:
                try:
                    await self.repository.create(body)
                except ServiceError as conflict:
                    if conflict.status != 409:
                        raise
            elif error.status != 412:
                raise

    @staticmethod
    def revalidate(value: dict[str, Any]) -> Scenario:
        try:
            return Scenario.model_validate(value)
        except ValidationError as error:
            raise ServiceError(422, str(error.errors()[0]["msg"])) from error
