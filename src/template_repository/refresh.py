"""Scheduled Container Apps Job: python -m template_repository.refresh.

Requires explicit REFRESH_ENABLED=true and the same live settings as the API.
Only recently optimized, nonexpired scenarios are eligible; no public listing.
The frontend must submit/poll a new run to observe newly refreshed metrics.
"""

import asyncio
import logging
import time

from template_repository.config import Settings, get_settings
from template_repository.errors import ServiceError
from template_repository.logging_config import configure_logging
from template_repository.models.scenario import Scenario
from template_repository.runtime import Runtime
from template_repository.telemetry import configure_telemetry

logger = logging.getLogger(__name__)


async def refresh(settings: Settings) -> int:
    if not settings.refresh_enabled:
        logger.info("refresh_disabled")
        return 0
    # Refresh must actually recompute observations, not reuse cached route results.
    settings = settings.model_copy(update={"maps_cache_seconds": 0})
    runtime = Runtime(settings)
    count = 0
    failures = 0
    try:
        await runtime.start()
        active = await runtime.repository.active_scenarios(
            settings.refresh_max_scenarios, time.time() - 3600
        )
        for document in active:
            try:
                scenario, _ = await runtime.scenarios.get(document.body["scenario_id"])
                # The initial "active" window is intentionally not renewed by cron.
                await _refresh_one(runtime, scenario)
                count += 1
            except ServiceError as error:
                if error.status == 404:
                    continue
                failures += 1
                logger.exception(
                    "scenario_refresh_failed", extra={"scenario_id": document.body["scenario_id"]}
                )
    finally:
        await runtime.close()
    logger.info("refresh_complete", extra={"refreshed_scenarios": count})
    if failures:
        raise ServiceError(503, f"{failures} scenario refreshes failed; see structured logs.")
    return count


async def _refresh_one(runtime: Runtime, scenario: Scenario) -> None:
    run = await runtime.runs.submit(scenario, mark_active=False)
    await asyncio.gather(*runtime.runs.tasks)
    result, _ = await runtime.runs.get(scenario.id, run.id)
    if result.status == "failed":
        raise ServiceError(503, result.error or "Refresh failed.")


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_telemetry(settings)
    asyncio.run(refresh(settings))


if __name__ == "__main__":
    main()
