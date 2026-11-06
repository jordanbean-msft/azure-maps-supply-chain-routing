from pydantic import Field

from template_repository.models.domain_model import DomainModel


class CostProfile(DomainModel):
    currency: str = Field(default="USD", pattern=r"^(USD|CAD|EUR|GBP)$")
    distance_cost_per_km: float = Field(default=0.5, ge=0, le=100)
    driver_cost_per_hour: float = Field(default=30, ge=0, le=1000)
    fuel_price_per_liter: float = Field(default=1.5, ge=0, le=100)
    fuel_liters_per_100_km: float = Field(default=30, ge=0, le=100)
    emissions_kg_per_liter: float = Field(default=2.68, ge=0, le=10)
    carbon_cost_per_kg: float = Field(default=0.1, ge=0, le=10)
    delay_penalty_per_hour: float = Field(default=50, ge=0, le=1000)
