from pydantic import Field

from template_repository.models.domain_model import DomainModel


class GeocodeResult(DomainModel):
    address: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
