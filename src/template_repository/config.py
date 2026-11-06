from typing import Literal

from pydantic import Field
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


def get_settings() -> Settings:
    return Settings()
