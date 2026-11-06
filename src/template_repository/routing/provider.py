from typing import Protocol

from template_repository.models.geocode_result import GeocodeResult
from template_repository.models.route_candidate import RouteCandidate
from template_repository.models.scenario import Scenario


class RoutingProvider(Protocol):
    async def geocode(self, address: str) -> list[GeocodeResult]: ...

    async def routes(self, scenario: Scenario) -> tuple[list[RouteCandidate], list[str]]: ...
