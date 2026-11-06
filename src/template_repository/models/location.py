from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator

from template_repository.models.domain_model import DomainModel


class Location(DomainModel):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["supplier", "factory"]
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: str = Field(default="", max_length=500)
    quantity: float = Field(
        ge=0, le=100000, description="Supply/capacity; at most 3 decimal places."
    )

    @field_validator("quantity")
    @classmethod
    def bounded_precision(cls, value: float) -> float:
        if Decimal(str(value)) * 1000 != (Decimal(str(value)) * 1000).to_integral_value():
            raise ValueError("Quantity supports at most three decimal places.")
        return value
