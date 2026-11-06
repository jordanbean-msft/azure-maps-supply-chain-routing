import math

from template_repository.models.geocode_result import GeocodeResult
from template_repository.models.route_candidate import RouteCandidate
from template_repository.models.scenario import Scenario
from template_repository.routing.identifiers import route_id


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    a = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 6371 * 2 * math.asin(min(1, math.sqrt(a)))


class SimulatedRouting:
    async def geocode(self, address: str) -> list[GeocodeResult]:
        cities = {
            "houston": (29.7604, -95.3698),
            "katy": (29.7858, -95.8245),
            "pasadena": (29.6911, -95.2091),
            "baytown": (29.7355, -94.9774),
            "sugar land": (29.6197, -95.6349),
            "seattle": (47.6062, -122.3321),
            "tacoma": (47.2529, -122.4443),
            "spokane": (47.6588, -117.426),
            "portland": (45.5152, -122.6784),
            "yakima": (46.6021, -120.5059),
        }
        return [
            GeocodeResult(
                address=f"{city.title()} (simulated city center)", latitude=lat, longitude=lon
            )
            for city, (lat, lon) in cities.items()
            if city in address.lower()
        ]

    async def routes(self, scenario: Scenario) -> tuple[list[RouteCandidate], list[str]]:
        routes = []
        for supplier in scenario.locations:
            if supplier.kind != "supplier":
                continue
            for factory in scenario.locations:
                if factory.kind != "factory":
                    continue
                direct = distance_km(
                    supplier.latitude, supplier.longitude, factory.latitude, factory.longitude
                )
                for index in range(2):
                    distance = direct * (1.2 + index * 0.13)
                    base_minutes = distance / min(scenario.truck.max_speed_kph, 75) * 60
                    traffic = base_minutes * (0.12 if index == 0 else 0.04)
                    routes.append(
                        RouteCandidate(
                            id=route_id(supplier.id, factory.id, index),
                            supplier_id=supplier.id,
                            factory_id=factory.id,
                            geometry=[
                                (supplier.longitude, supplier.latitude),
                                (
                                    (supplier.longitude + factory.longitude) / 2
                                    + 0.03 * (index + 1),
                                    (supplier.latitude + factory.latitude) / 2,
                                ),
                                (factory.longitude, factory.latitude),
                            ],
                            distance_km=distance,
                            duration_minutes=base_minutes + traffic,
                            traffic_delay_minutes=traffic,
                            weather_risk=0.1,
                            weather_delay_minutes=base_minutes * 0.02,
                            toll_estimate=distance * (0.02 if index == 0 else 0),
                            source="simulated",
                        )
                    )
        return routes, [
            "All roads, traffic and weather are deterministic simulations, not navigable directions.",
            "Tolls and weather delays are estimates; costs scale linearly per shipment unit.",
        ]
