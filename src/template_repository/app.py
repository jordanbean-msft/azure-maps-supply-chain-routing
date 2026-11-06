import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response

from template_repository.config import Settings, get_settings
from template_repository.logging_config import configure_logging
from template_repository.models.app_config import AppConfig
from template_repository.models.maps_token import MapsToken

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_logging(configuration.log_level)
        logger.info("application_startup", extra={"app_mode": configuration.app_mode})
        yield
        logger.info("application_shutdown")

    application = FastAPI(title="Supply Chain Routing", lifespan=lifespan)
    application.state.settings = configuration

    @application.get("/health")
    @application.get("/health/live")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/health/ready")
    async def ready(response: Response) -> dict[str, str]:
        if configuration.app_mode == "live":
            # Dependency probes are added with the backend service implementations.
            response.status_code = 503
            return {"status": "not_ready", "reason": "live_services_not_initialized"}
        return {"status": "ok", "mode": "demo"}

    @application.get("/api/config")
    async def app_config() -> AppConfig:
        return AppConfig(
            mode=configuration.app_mode,
            routing_source="simulated" if configuration.app_mode == "demo" else "azure_maps",
            routing_available=configuration.app_mode == "demo",
            maps_available=False,
            persistence="memory" if configuration.app_mode == "demo" else "cosmos",
        )

    @application.get("/api/maps/token", response_model=MapsToken)
    async def maps_token() -> MapsToken:
        raise HTTPException(
            status_code=503,
            detail="Live Azure Maps authentication is not available in this foundation.",
        )

    return application


app = create_app()
