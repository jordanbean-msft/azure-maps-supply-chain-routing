from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import metrics, trace

from template_repository.config import Settings

tracer = trace.get_tracer("template_repository")
meter = metrics.get_meter("template_repository")
maps_requests = meter.create_counter("maps.requests", unit="{request}")
upstream_latency = meter.create_histogram("maps.duration", unit="s")
optimization_latency = meter.create_histogram("optimization.duration", unit="s")
solver_latency = meter.create_histogram("solver.duration", unit="s")
route_count = meter.create_histogram("optimization.routes", unit="{route}")
run_failures = meter.create_counter("optimization.failures", unit="{run}")
cache_hits = meter.create_counter("cache.hits", unit="{hit}")
cosmos_charge = meter.create_counter("cosmos.request_charge", unit="{RU}")


def configure_telemetry(settings: Settings) -> None:
    if settings.telemetry_enabled and settings.applicationinsights_connection_string:
        configure_azure_monitor(
            connection_string=settings.applicationinsights_connection_string,
            logger_name="template_repository",
            enable_live_metrics=False,
            instrumentation_options={
                "azure_sdk": {"enabled": True},
                "httpx": {"enabled": True},
                "fastapi": {"enabled": False},
            },
        )
