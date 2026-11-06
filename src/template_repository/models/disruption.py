from typing import Literal, Self

from pydantic import Field, model_validator

from template_repository.models.domain_model import DomainModel


class Disruption(DomainModel):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    kind: Literal["road_closure", "facility_delay", "weather", "fuel_price"]
    name: str = Field(min_length=1, max_length=100)
    route_id: str | None = Field(
        default=None, min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$"
    )
    location_id: str | None = Field(
        default=None, min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$"
    )
    delay_minutes: float = Field(default=0, ge=0, le=1440)
    severity: float = Field(default=0, ge=0, le=1)
    fuel_price_per_liter: float | None = Field(default=None, ge=0, le=100)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_semantics(self) -> Self:
        if self.kind == "road_closure":
            valid = (
                bool(self.route_id)
                and self.location_id is None
                and not self.delay_minutes
                and not self.severity
                and self.fuel_price_per_liter is None
            )
        elif self.kind == "facility_delay":
            valid = (
                bool(self.location_id)
                and self.route_id is None
                and self.delay_minutes > 0
                and not self.severity
                and self.fuel_price_per_liter is None
            )
        elif self.kind == "weather":
            valid = (
                not (self.route_id and self.location_id)
                and not self.delay_minutes
                and self.fuel_price_per_liter is None
            )
        else:
            valid = (
                self.fuel_price_per_liter is not None
                and self.route_id is None
                and self.location_id is None
                and not self.delay_minutes
                and not self.severity
            )
        if not valid:
            raise ValueError(
                "Disruption requires its kind-specific target/value; unrelated fields are forbidden."
            )
        return self
