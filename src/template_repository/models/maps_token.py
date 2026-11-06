from pydantic import AwareDatetime

from template_repository.models.domain_model import DomainModel


class MapsToken(DomainModel):
    token: str
    client_id: str
    expires_on: AwareDatetime
