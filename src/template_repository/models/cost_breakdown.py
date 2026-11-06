from pydantic import Field

from template_repository.models.domain_model import DomainModel


class CostBreakdown(DomainModel):
    distance_cost: float = Field(default=0, ge=0)
    driver_time_cost: float = Field(default=0, ge=0)
    toll_cost: float = Field(default=0, ge=0)
    fuel_cost: float = Field(default=0, ge=0)
    carbon_cost: float = Field(default=0, ge=0)
    traffic_delay_penalty: float = Field(default=0, ge=0)
    weather_delay_penalty: float = Field(default=0, ge=0)
    simulated_disruption_penalty: float = Field(default=0, ge=0)
    total: float = Field(default=0, ge=0)
