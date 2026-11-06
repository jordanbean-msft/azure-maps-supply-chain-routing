from typing import Literal

from pydantic import Field

from template_repository.models.domain_model import DomainModel


class Location(DomainModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["supplier", "factory"]
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: str = Field(default="", max_length=500)
    quantity: float = Field(ge=0, description="Supplier supply or factory capacity in units.")
