from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FabricSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FABRIC_", env_file=".env", extra="ignore")

    workspace_name: str = "supply-chain-routing"
    workspace_id: str = ""
    capacity_id: str
    lakehouse_name: str = "delivery_carbon"
    maps_client_id: str
    key_vault_url: str
    maps_secret_name: str = "azure-maps-key"
    carbon_price_usd_per_tonne: float = Field(default=100, ge=0, allow_inf_nan=False)
    workbook: Path = Path("sample/Houston_Delivery_CO2.xlsx")
    baseline_csv: Path = Path("sample/Houston_Delivery_CO2_Live_20261109_1208.csv")
