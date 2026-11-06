from pydantic import Field

from template_repository.models.domain_model import DomainModel


class TruckProfile(DomainModel):
    height_m: float = Field(default=4, gt=0, le=5)
    width_m: float = Field(default=2.5, gt=0, le=3)
    length_m: float = Field(default=16.5, gt=0, le=30)
    weight_kg: float = Field(default=20000, ge=1, le=100000, multiple_of=1)
    max_speed_kph: float = Field(default=90, ge=1, le=160, multiple_of=1)
