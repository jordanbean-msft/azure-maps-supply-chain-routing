from pydantic import Field

from template_repository.models.domain_model import DomainModel


class GeocodeRequest(DomainModel):
    address: str = Field(min_length=1, max_length=500)
