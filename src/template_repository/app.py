import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus

from azure.core.exceptions import AzureError
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.exceptions import HTTPException

from template_repository.api import create_router
from template_repository.config import Settings, get_settings
from template_repository.errors import ServiceError
from template_repository.logging_config import configure_logging
from template_repository.middleware import GuardMiddleware
from template_repository.models.problem_details import ProblemDetails
from template_repository.persistence.repository import Repository
from template_repository.routing.provider import RoutingProvider
from template_repository.runtime import Runtime
from template_repository.telemetry import configure_telemetry

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    repository: Repository | None = None,
    routing: RoutingProvider | None = None,
) -> FastAPI:
    configuration = settings or get_settings()
    runtime = Runtime(configuration, repository, routing)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_logging(configuration.log_level)
        configure_telemetry(configuration)
        logger.info("application_startup", extra={"app_mode": configuration.app_mode})
        try:
            try:
                await runtime.start()
            except (ServiceError, AzureError, TimeoutError):
                logger.exception("live_initialization_failed")
            yield
        finally:
            await runtime.close()
            logger.info("application_shutdown")

    application = FastAPI(
        title="Supply Chain Routing",
        lifespan=lifespan,
        responses={
            status: {
                "description": HTTPStatus(status).phrase,
                "content": {
                    "application/problem+json": {"schema": ProblemDetails.model_json_schema()}
                },
            }
            for status in (403, 404, 409, 412, 413, 422, 428, 429, 500, 503)
        },
    )
    application.state.settings = configuration
    application.state.runtime = runtime
    application.add_middleware(GuardMiddleware, settings=configuration)
    application.include_router(create_router(runtime))

    def problem(request: Request, status: int, detail: str) -> JSONResponse:
        return JSONResponse(
            ProblemDetails(
                title=HTTPStatus(status).phrase,
                status=status,
                detail=detail,
                instance=request.url.path,
            ).model_dump(mode="json"),
            status_code=status,
            media_type="application/problem+json",
        )

    @application.exception_handler(ServiceError)
    async def service_error(request: Request, error: ServiceError) -> JSONResponse:
        return problem(request, error.status, error.detail)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        # Do not echo request bodies (which could contain private addresses).
        return problem(
            request,
            422,
            "; ".join(
                f"{'.'.join(map(str, item['loc']))}: {item['msg']}" for item in error.errors()[:5]
            ),
        )

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        return problem(request, error.status_code, str(error.detail))

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        logger.exception("request_unexpected_failure")
        return problem(request, 500, "Unexpected service failure.")

    if configuration.telemetry_enabled and configuration.applicationinsights_connection_string:
        FastAPIInstrumentor.instrument_app(application)

    return application


app = create_app()
