import asyncio
import hashlib
import json
import logging
import math
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import AzureError
from pydantic import TypeAdapter, ValidationError

from template_repository.config import Settings
from template_repository.errors import ServiceError
from template_repository.middleware import request_id_context
from template_repository.models.geocode_result import GeocodeResult
from template_repository.models.location import Location
from template_repository.models.route_candidate import Coordinate, RouteCandidate
from template_repository.models.scenario import Scenario
from template_repository.persistence.repository import Repository
from template_repository.routing.identifiers import route_id
from template_repository.routing.weather_sampling import forecast_samples
from template_repository.telemetry import cache_hits, maps_requests, upstream_latency

logger = logging.getLogger(__name__)
API_VERSION = "2025-01-01"


def _number(value: Any) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError("Invalid upstream numeric value")
    return float(value)


class AzureMapsRouting:
    """REST v2025 routing/search and Weather 1.1; no deprecated Route v1 schema."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        credential: AsyncTokenCredential,
        settings: Settings,
        repository: Repository,
    ) -> None:
        self.http = http
        self.credential = credential
        self.settings = settings
        self.repository = repository
        self._semaphore = asyncio.Semaphore(4)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            token = await self.credential.get_token("https://atlas.microsoft.com/.default")
        except AzureError as error:
            raise ServiceError(503, "Azure Maps identity unavailable.") from error
        headers = {
            "Authorization": f"Bearer {token.token}",
            "x-ms-client-id": self.settings.azure_maps_client_id or "",
            "Content-Type": "application/geo+json",
            "x-ms-client-request-id": request_id_context.get() or uuid4().hex,
        }
        async with self._semaphore:
            for attempt in range(3):
                started = time.monotonic()
                try:
                    response = await self.http.request(
                        method,
                        self.settings.azure_maps_endpoint + path,
                        params=params or {"api-version": API_VERSION},
                        json=body,
                        headers=headers,
                    )
                except httpx.RequestError as error:
                    if attempt == 2:
                        raise ServiceError(503, "Azure Maps transport unavailable.") from error
                    await asyncio.sleep(0.1 * 2**attempt)
                    continue
                maps_requests.add(1, {"operation": path, "status": response.status_code})
                upstream_latency.record(time.monotonic() - started, {"operation": path})
                if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    retry = response.headers.get("Retry-After", "")
                    await asyncio.sleep(
                        min(float(retry), 2) if retry.isdigit() else 0.1 * 2**attempt
                    )
                    continue
                if response.status_code != 200:
                    raise ServiceError(
                        503, f"Azure Maps {path} unavailable (HTTP {response.status_code})."
                    )
                try:
                    value = response.json()
                    if not isinstance(value, dict):
                        raise ValueError("Object required")
                    return value
                except ValueError as error:
                    raise ServiceError(503, "Azure Maps returned malformed JSON.") from error
        raise ServiceError(503, "Azure Maps retry budget exhausted.")

    async def geocode(self, address: str) -> list[GeocodeResult]:
        value = await self.request(
            "GET", "/geocode", params={"api-version": API_VERSION, "query": address, "top": "5"}
        )
        try:
            return [
                GeocodeResult(
                    address=feature["properties"]["address"]["formattedAddress"],
                    longitude=feature["geometry"]["coordinates"][0],
                    latitude=feature["geometry"]["coordinates"][1],
                )
                for feature in value["features"][:5]
            ]
        except (KeyError, TypeError, IndexError, ValidationError) as error:
            raise ServiceError(503, "Azure Maps geocoding response is malformed.") from error

    @staticmethod
    def _spec(scenario: Scenario) -> dict[str, Any]:
        return {
            "height": scenario.truck.height_m,
            "width": scenario.truck.width_m,
            "length": scenario.truck.length_m,
            "weight": round(scenario.truck.weight_kg),
            "maxSpeed": round(scenario.truck.max_speed_kph),
            "isVehicleCommercial": True,
        }

    async def _weather(
        self, scenario: Scenario, route: RouteCandidate, geometry: list[Coordinate]
    ) -> tuple[float, float, list[str]]:
        samples, covered_minutes, warnings = forecast_samples(
            geometry, route.duration_minutes, scenario.departure_time, datetime.now(UTC)
        )
        if not samples:
            return 0, 0, [f"{route.id}: {warning}" for warning in warnings]
        value = await self.request(
            "GET",
            "/weather/route/json",
            params={
                "api-version": "1.1",
                "query": ":".join(
                    f"{latitude:.6f},{longitude:.6f},{eta:.3f}"
                    for latitude, longitude, eta in samples
                ),
            },
        )
        try:
            waypoints = value["waypoints"]
            if not isinstance(waypoints, list) or len(waypoints) != len(samples):
                raise ValueError("Missing waypoint forecast coverage")
            indexes = [
                value["summary"]["hazards"]["maxHazardIndex"],
                *(point["hazards"]["maxHazardIndex"] for point in waypoints),
            ]
            if any(type(index) is not int or not 0 <= index <= 4 for index in indexes):
                raise ValueError("Invalid hazard index")
            risk = max(indexes) / 4
            return (
                risk,
                covered_minutes * risk * 0.3,
                [f"{route.id}: {warning}" for warning in warnings],
            )
        except (KeyError, TypeError, IndexError, ValueError) as error:
            raise ServiceError(
                503, "Azure Maps route weather response is incomplete or malformed."
            ) from error

    async def _directions(
        self, scenario: Scenario, supplier: Location, factory: Location
    ) -> tuple[list[RouteCandidate], list[str]]:
        body = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [point.longitude, point.latitude]},
                    "properties": {"pointType": "waypoint", "pointIndex": index},
                }
                for index, point in enumerate((supplier, factory))
            ],
            "travelMode": "truck",
            "vehicleSpec": self._spec(scenario),
            "optimizeRoute": "fastestWithTraffic",
            "routeOutputOptions": ["routePath"],
            "maxRouteCount": 2,
        }
        if scenario.departure_time > datetime.now(UTC):
            body["departAt"] = scenario.departure_time.isoformat()
        value = await self.request("POST", "/route/directions", body=body)
        warnings = []
        if "departAt" not in body:
            warnings.append(
                "Selected departure is in the past; routing and weather use current departure instead."
            )
        routes = []
        road_geometries = []
        try:
            alternatives = value.get("alternativeRoutes", [])
            if not isinstance(alternatives, list):
                raise ValueError("Invalid alternatives")
            for index, collection in enumerate([value, *alternatives[:1]]):
                paths = [
                    feature
                    for feature in collection["features"]
                    if feature["properties"]["type"] == "RoutePath"
                ]
                if len(paths) != 1:
                    raise ValueError("Exactly one RoutePath required")
                path = paths[0]
                properties = path["properties"]
                if any(leg.get("travelMode") == "other" for leg in properties.get("legs", [])):
                    warnings.append(
                        f"Truck coverage incomplete for {supplier.name} → {factory.name}."
                    )
                geometry = TypeAdapter(list[Coordinate]).validate_python(
                    [coordinate for leg in path["geometry"]["coordinates"] for coordinate in leg]
                )
                road_geometries.append(geometry)
                # Bound Cosmos snapshots while retaining endpoints.
                stride = max(1, math.ceil(len(geometry) / 250))
                sampled = geometry[::stride]
                if sampled[-1] != geometry[-1]:
                    sampled.append(geometry[-1])
                duration = _number(properties["durationTrafficInSeconds"]) / 60
                base = _number(properties["durationInSeconds"]) / 60
                routes.append(
                    RouteCandidate(
                        id=route_id(supplier.id, factory.id, index),
                        supplier_id=supplier.id,
                        factory_id=factory.id,
                        geometry=sampled,
                        distance_km=_number(properties["distanceInMeters"]) / 1000,
                        duration_minutes=duration,
                        traffic_delay_minutes=max(0, duration - base),
                        toll_estimate=0,
                        source="azure_maps",
                    )
                )
        except (KeyError, TypeError, IndexError, ValueError, ValidationError) as error:
            raise ServiceError(503, "Azure Maps directions response is malformed.") from error
        # Forecast each alternative's own road path, not the endpoints' midpoint.
        for route, geometry in zip(routes, road_geometries, strict=True):
            try:
                risk, delay, coverage_warnings = await self._weather(scenario, route, geometry)
                route.weather_risk, route.weather_delay_minutes = risk, delay
                warnings.extend(coverage_warnings)
            except ServiceError:
                warnings.append(
                    f"Weather unavailable or incomplete for {route.id}; zero weather adjustment is not an observation."
                )
        return routes, warnings

    async def routes(self, scenario: Scenario) -> tuple[list[RouteCandidate], list[str]]:
        signature = {
            "routing_version": API_VERSION,
            "weather_version": "route-1.1",
            "locations": [x.model_dump(mode="json") for x in scenario.locations],
            "truck": scenario.truck.model_dump(),
            "departure_time": scenario.departure_time.isoformat(),
        }
        key = "maps-" + hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
        try:
            cached = await self.repository.get(scenario.id, key)
            cache_hits.add(1, {"kind": "routes"})
            return [
                RouteCandidate.model_validate(route) for route in cached.body["routes"]
            ], cached.body["warnings"]
        except ServiceError as error:
            if error.status != 404:
                raise
        suppliers = [x for x in scenario.locations if x.kind == "supplier"]
        factories = [x for x in scenario.locations if x.kind == "factory"]
        body = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "MultiPoint",
                        "coordinates": [[x.longitude, x.latitude] for x in points],
                    },
                    "properties": {"pointType": kind},
                }
                for kind, points in (("origins", suppliers), ("destinations", factories))
            ],
            "travelMode": "truck",
            "vehicleSpec": self._spec(scenario),
            "traffic": "live",
            "departAt": scenario.departure_time.isoformat()
            if scenario.departure_time > datetime.now(UTC)
            else "now",
        }
        matrix = await self.request("POST", "/route/matrix", body=body)
        try:
            cells = matrix["properties"]["matrix"]
            expected = {(i, j) for i in range(len(suppliers)) for j in range(len(factories))}
            seen = set()
            lanes = []
            for cell in cells:
                pair = cell["originIndex"], cell["destinationIndex"]
                if pair not in expected or pair in seen:
                    raise ValueError("Unexpected matrix cell")
                seen.add(pair)
                if cell["statusCode"] == 404:
                    continue
                if cell["statusCode"] != 200:
                    raise ServiceError(503, "Azure Maps matrix contains failed cells.")
                _number(cell["distanceInMeters"])
                _number(cell["durationTrafficInSeconds"])
                lanes.append((suppliers[pair[0]], factories[pair[1]]))
            if seen != expected:
                raise ValueError("Incomplete matrix")
        except (KeyError, TypeError, IndexError, ValueError) as error:
            raise ServiceError(503, "Azure Maps matrix response is malformed.") from error
        results = await asyncio.gather(
            *(self._directions(scenario, supplier, factory) for supplier, factory in lanes)
        )
        routes = [route for candidates, _ in results for route in candidates]
        warnings = [
            "Tolls are unavailable from this API: zero is an unpriced estimate, not a toll-free guarantee.",
            "Weather risk/delay are estimates from sampled road-vertex forecasts within 120 minutes "
            "of now; pass-through times are distance-proportional estimates and unsampled conditions are unknown.",
            "Allocation costs scale linearly per unit; truck profile is a routing assumption, not fleet dispatch.",
        ] + [warning for _, values in results for warning in values]
        if body["departAt"] == "now":
            warnings.append(
                "Selected departure is in the past; routing and weather use current departure instead."
            )
        warnings = list(dict.fromkeys(warnings))
        if self.settings.maps_cache_seconds:
            try:
                await self.repository.create(
                    {
                        "id": key,
                        "scenario_id": scenario.id,
                        "kind": "maps_cache",
                        "ttl": self.settings.maps_cache_seconds,
                        "routes": [route.model_dump(mode="json") for route in routes],
                        "warnings": warnings,
                    }
                )
            except ServiceError as error:
                if error.status != 409:
                    raise
        return routes, warnings
