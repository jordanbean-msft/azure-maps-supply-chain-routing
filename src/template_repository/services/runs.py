import asyncio
import hashlib
import logging
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from template_repository.config import Settings
from template_repository.errors import ServiceError
from template_repository.models.optimization_run import OptimizationRun
from template_repository.models.run_event import RunEvent
from template_repository.models.scenario import Scenario
from template_repository.optimization.engine import optimize
from template_repository.persistence.repository import Document, Repository
from template_repository.routing.provider import RoutingProvider
from template_repository.services.scenarios import ScenarioService
from template_repository.telemetry import (
    optimization_latency,
    route_count,
    run_failures,
    solver_latency,
    tracer,
)

logger = logging.getLogger(__name__)
TERMINAL = {"completed", "failed", "infeasible"}


class RunService:
    def __init__(
        self, repository: Repository, routing: RoutingProvider, settings: Settings
    ) -> None:
        self.repository = repository
        self.routing = routing
        self.settings = settings
        self.tasks: set[asyncio.Task[None]] = set()
        self._lock = asyncio.Lock()

    async def submit(
        self, scenario: Scenario, idempotency_key: str | None = None, *, mark_active: bool = True
    ) -> OptimizationRun:
        scenario = scenario.model_copy(deep=True)
        if not any(x.kind == "supplier" and x.quantity > 0 for x in scenario.locations) or not any(
            x.kind == "factory" for x in scenario.locations
        ):
            raise ServiceError(422, "Optimization requires positive supplier supply and a factory.")
        identifier = "run-" + (
            hashlib.sha256(f"{scenario.id}:{idempotency_key}".encode()).hexdigest()
            if idempotency_key
            else uuid4().hex
        )
        async with self._lock:
            if idempotency_key:
                try:
                    return (await self.get(scenario.id, identifier))[0]
                except ServiceError as error:
                    if error.status != 404:
                        raise
            if len(self.tasks) >= self.settings.max_concurrent_runs:
                raise ServiceError(429, "Optimization concurrency budget reached.")
            now = datetime.now(UTC)
            run = OptimizationRun(
                id=identifier, scenario_id=scenario.id, created_at=now, updated_at=now
            )
            document = {
                "id": identifier,
                "scenario_id": scenario.id,
                "kind": "run",
                "ttl": self.settings.snapshot_ttl_seconds,
                "deadline": time.time() + self.settings.run_timeout_seconds,
                "snapshot": scenario.model_dump(mode="json"),
                "run": run.model_dump(mode="json"),
                "events": [self._event(run, 1)],
            }
            try:
                await self.repository.create(document)
            except ServiceError as error:
                if error.status == 409 and idempotency_key:
                    return (await self.get(scenario.id, identifier))[0]
                raise
            task = asyncio.create_task(self._execute(scenario, run, mark_active=mark_active))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
            return run

    @staticmethod
    def _event(run: OptimizationRun, sequence: int) -> dict[str, Any]:
        return RunEvent(
            sequence=sequence,
            run_id=run.id,
            status=run.status,
            stage=run.stage,
            progress=run.progress,
            message=run.error or run.stage,
        ).model_dump(mode="json")

    async def get(self, scenario_id: str, run_id: str) -> tuple[OptimizationRun, Document]:
        document = await self.repository.get(scenario_id, run_id)
        if document.body.get("kind") != "run":
            raise ServiceError(404, "Run not found.")
        run = OptimizationRun.model_validate(document.body["run"])
        if run.status not in TERMINAL and document.body["deadline"] < time.time():
            run.status, run.stage, run.progress = "failed", "expired", 1
            run.error = (
                "Worker lease expired; submit a new run (the prior worker may have restarted)."
            )
            run.updated_at = datetime.now(UTC)
            try:
                document = await self._write(run, document)
            except ServiceError as error:
                if error.status != 412:
                    raise
                document = await self.repository.get(scenario_id, run_id)
                run = OptimizationRun.model_validate(document.body["run"])
        return run, document

    async def _write(
        self, run: OptimizationRun, current: Document, candidate_ids: list[str] | None = None
    ) -> Document:
        body = current.body
        body["run"] = run.model_dump(mode="json")
        body["events"].append(self._event(run, len(body["events"]) + 1))
        if candidate_ids is not None:
            body["candidate_ids"] = candidate_ids
        return await self.repository.replace(body, current.etag)

    async def _stage(
        self,
        run: OptimizationRun,
        stage: str,
        progress: float,
        candidate_ids: list[str] | None = None,
    ) -> None:
        current_run, document = await self.get(run.scenario_id, run.id)
        if current_run.status in TERMINAL:
            raise ServiceError(409, "Run has already terminated.")
        run.stage, run.progress, run.updated_at = stage, progress, datetime.now(UTC)
        await self._write(run, document, candidate_ids)
        logger.info(
            "optimization_stage",
            extra={"scenario_id": run.scenario_id, "run_id": run.id, "stage": stage},
        )

    async def _execute(
        self, scenario: Scenario, run: OptimizationRun, *, mark_active: bool = True
    ) -> None:
        started = time.monotonic()
        try:
            async with asyncio.timeout(self.settings.run_timeout_seconds):
                with tracer.start_as_current_span("optimization") as span:
                    span.set_attribute("scenario_id", scenario.id)
                    run.status = "running"
                    await self._stage(run, "routing", 0.1)
                    routes, warnings = await self.routing.routes(scenario)
                    route_count.record(len(routes))
                    run.warnings = [
                        *warnings,
                        "Solver precision: quantities 0.001 units; objective coefficients 0.001 currency units.",
                    ]
                    await self._stage(run, "optimizing", 0.65)
                    solver_started = time.monotonic()
                    allocations, routes_for_display = await asyncio.to_thread(
                        optimize, scenario, routes
                    )
                    solver_latency.record(time.monotonic() - solver_started)
                    run.routes, run.allocations = routes_for_display, allocations
                    run.total_cost = sum(x.total_cost for x in allocations)
                    run.status = "completed" if allocations else "infeasible"
                    if not allocations:
                        run.warnings.append(
                            "Supply cannot be fully assigned under capacity and route constraints."
                        )
                    await self._stage(run, run.status, 1, [route.id for route in routes])
                    latest = {
                        "id": "latest",
                        "scenario_id": scenario.id,
                        "kind": "latest",
                        "ttl": self.settings.snapshot_ttl_seconds,
                        "run_id": run.id,
                    }
                    try:
                        existing = await self.repository.get(scenario.id, "latest")
                    except ServiceError as error:
                        if error.status != 404:
                            raise
                        try:
                            await self.repository.create(latest)
                        except ServiceError as conflict:
                            if conflict.status != 409:
                                raise
                    else:
                        try:
                            await self.repository.replace(latest, existing.etag)
                        except ServiceError as conflict:
                            if conflict.status != 412:
                                raise
                    if mark_active:
                        await ScenarioService(self.repository, self.settings).mark_active(scenario)
        except asyncio.CancelledError:
            await self._fail(run, "Worker stopped during shutdown; submit a new run.")
            raise
        except (ServiceError, TimeoutError) as error:
            await self._fail(
                run,
                error.detail
                if isinstance(error, ServiceError)
                else "Optimization deadline exceeded.",
            )
        except Exception:
            # Task boundary: persist a safe terminal result for unexpected worker faults.
            logger.exception(
                "optimization_unexpected_failure",
                extra={"scenario_id": scenario.id, "run_id": run.id},
            )
            await self._fail(run, "Unexpected optimization failure.")
        finally:
            optimization_latency.record(time.monotonic() - started)

    async def _fail(self, run: OptimizationRun, message: str) -> None:
        run_failures.add(1)
        logger.warning(
            "optimization_failed",
            extra={"run_id": run.id, "scenario_id": run.scenario_id, "error": message},
        )
        try:
            current, document = await self.get(run.scenario_id, run.id)
            if current.status in TERMINAL:
                return
            run.status, run.stage, run.progress, run.error = "failed", "failed", 1, message
            run.allocations, run.total_cost = [], 0
            run.updated_at = datetime.now(UTC)
            await self._write(run, document)
        except ServiceError:
            logger.exception("run_failure_persistence_unavailable", extra={"run_id": run.id})

    async def close(self) -> None:
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
