from typing import Self

from pydantic import AwareDatetime, Field, model_validator

from template_repository.models.cost_profile import CostProfile
from template_repository.models.disruption import Disruption
from template_repository.models.domain_model import DomainModel
from template_repository.models.location import Location
from template_repository.models.truck_profile import TruckProfile


class Scenario(DomainModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    locations: list[Location] = Field(default_factory=list, max_length=13)
    cost_profile: CostProfile = Field(default_factory=CostProfile)
    disruptions: list[Disruption] = Field(default_factory=list, max_length=30)
    departure_time: AwareDatetime
    truck: TruckProfile = Field(default_factory=TruckProfile)

    @model_validator(mode="after")
    def validate_locations(self) -> Self:
        ids = [location.id for location in self.locations]
        if len(set(ids)) != len(ids):
            raise ValueError("Location IDs must be unique.")
        if sum(location.kind == "supplier" for location in self.locations) > 10:
            raise ValueError("At most 10 suppliers are allowed.")
        if sum(location.kind == "factory" for location in self.locations) > 3:
            raise ValueError("At most 3 factories are allowed.")
        disruption_ids = [disruption.id for disruption in self.disruptions]
        if len(set(disruption_ids)) != len(disruption_ids):
            raise ValueError("Disruption IDs must be unique.")
        return self
