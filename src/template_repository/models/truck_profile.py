from pydantic import Field

from template_repository.models.domain_model import DomainModel


class TruckProfile(DomainModel):
    height_m: float = Field(default=4, gt=0)
    width_m: float = Field(default=2.5, gt=0)
    length_m: float = Field(default=16.5, gt=0)
    weight_kg: float = Field(default=20000, gt=0)
    max_speed_kph: float = Field(default=90, gt=0, le=160)
