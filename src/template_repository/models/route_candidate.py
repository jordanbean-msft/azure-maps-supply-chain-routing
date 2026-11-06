from typing import Annotated, Literal

from pydantic import Field

from template_repository.models.domain_model import DomainModel

Coordinate = tuple[
    Annotated[float, Field(ge=-180, le=180)],
    Annotated[float, Field(ge=-90, le=90)],
]


class RouteCandidate(DomainModel):
    id: str = Field(min_length=1, max_length=100)
    supplier_id: str
    factory_id: str
    geometry: list[Coordinate] = Field(min_length=2, max_length=10000)
    distance_km: float = Field(ge=0)
    duration_minutes: float = Field(
        ge=0, description="Travel time including traffic, not weather/simulation."
    )
    traffic_delay_minutes: float = Field(default=0, ge=0)
    weather_delay_minutes: float = Field(default=0, ge=0)
    simulated_delay_minutes: float = Field(default=0, ge=0)
    toll_estimate: float = Field(default=0, ge=0)
    weather_risk: float = Field(default=0, ge=0, le=1)
    source: Literal["azure_maps", "simulated"]
