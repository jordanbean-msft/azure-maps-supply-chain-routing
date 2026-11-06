from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized runtime settings; demo mode requires no Azure credentials."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    port: int = Field(default=8000, ge=1, le=65535)
    host: str = "0.0.0.0"
    azure_environment: str = "development"
    app_mode: Literal["demo", "live"] = "demo"
    azure_client_id: str | None = None
    azure_maps_client_id: str | None = None
    azure_maps_endpoint: str = "https://atlas.microsoft.com"
    cosmos_endpoint: str | None = None
    cosmos_database: str = "supply-chain-routing"
    cosmos_container: str = "scenarios"
    snapshot_ttl_seconds: int = Field(default=3600, ge=60)
    scenario_ttl_seconds: int = Field(default=86400, ge=60)
    maps_allowed_origins: list[str] = Field(default_factory=list)
    maps_browser_client_id: str | None = None
    allow_developer_credentials: bool = False
    telemetry_enabled: bool = False
    applicationinsights_connection_string: str | None = None
    refresh_enabled: bool = False
    refresh_max_scenarios: int = Field(default=5, ge=1, le=20)
    run_timeout_seconds: int = Field(default=180, ge=1, le=600)
    max_concurrent_runs: int = Field(default=2, ge=1, le=5)
    requests_per_minute: int = Field(default=120, ge=1, le=1000)
    expensive_requests_per_minute: int = Field(default=10, ge=1, le=60)
    max_request_bytes: int = Field(default=65536, ge=1024, le=131072)
    maps_cache_seconds: int = Field(default=300, ge=0, le=3600)
    max_memory_documents: int = Field(default=1000, ge=10, le=10000)

    @model_validator(mode="after")
    def retention_covers_worker_lease(self) -> Self:
        if self.snapshot_ttl_seconds < self.run_timeout_seconds + 60:
            raise ValueError("Snapshot TTL must exceed the run timeout by at least 60 seconds.")
        return self


def get_settings() -> Settings:
    return Settings()
