from typing import Literal

from pydantic import Field

from template_repository.models.domain_model import DomainModel


class Disruption(DomainModel):
    id: str = Field(min_length=1, max_length=100)
    kind: Literal["road_closure", "facility_delay", "weather", "fuel_price"]
    name: str = Field(min_length=1, max_length=100)
    route_id: str | None = None
    location_id: str | None = None
    delay_minutes: float = Field(default=0, ge=0)
    severity: float = Field(default=0, ge=0, le=1)
    fuel_price_per_liter: float | None = Field(default=None, ge=0)
    enabled: bool = True
