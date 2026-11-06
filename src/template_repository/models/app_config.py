from typing import Literal

from template_repository.models.domain_model import DomainModel


class AppConfig(DomainModel):
    mode: Literal["demo", "live"]
    routing_source: Literal["simulated", "azure_maps"]
    routing_available: bool
    maps_available: bool
    persistence: Literal["memory", "cosmos"]
    max_suppliers: int = 10
    max_factories: int = 3
