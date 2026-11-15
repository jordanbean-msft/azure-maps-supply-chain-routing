import asyncio
import json
import logging
import math
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)
Row = dict[str, Any]
TokenProvider = Callable[[], Awaitable[str]]
API_VERSION = "2025-01-01"
ADDRESS_FIELDS = ("Street", "City", "RegionCode", "PstlCode", "CtryCode")
RESULT_FIELDS = {
    "Driving_distance_km",
    "CO2_emitted_kg",
    "Carbon_cost_USD",
    "Carbon_price_USD_per_tonne",
    "Route_geojson",
    "Route_Status",
    "Route_Error_Reason",
    "Route_Error_Detail",
    "Refreshed_UTC",
    "Supplier_address",
    "Plant_address",
    "Supplier_matched_address",
    "Plant_matched_address",
    "Supplier_route_latitude",
    "Supplier_route_longitude",
    "Plant_route_latitude",
    "Plant_route_longitude",
    "Input_signature",
}


def finite_number(value: Any, label: str, minimum: float = 0) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite number >= {minimum}.")
    result = float(value)
    if not math.isfinite(result) or result < minimum:
        raise ValueError(f"{label} must be a finite number >= {minimum}.")
    return result


def delivery_address(row: Row, prefix: str) -> str:
    values = [str(row.get(f"{prefix}_{name}") or "").strip() for name in ADDRESS_FIELDS]
    if not all(values):
        raise ValueError(f"{prefix} address is incomplete.")
    return ", ".join(values)


def coordinate(value: Any) -> list[float]:
    if not isinstance(value, list) or len(value) < 2:
        raise ValueError("Azure Maps returned an invalid coordinate.")
    lon, lat = float(value[0]), float(value[1])
    if not math.isfinite(lon) or not math.isfinite(lat) or abs(lon) > 180 or abs(lat) > 90:
        raise ValueError("Azure Maps returned an out-of-range coordinate.")
    return [lon, lat]


class DeliveryMaps:
    """Bounded sequential driver-side routing with per-run, directional caches."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        token_provider: TokenProvider | None,
        client_id: str,
        *,
        pace_seconds: float = 0.25,
        subscription_key_provider: TokenProvider | None = None,
    ) -> None:
        self.http = http
        self.token_provider = token_provider
        self.client_id = client_id
        self.pace_seconds = pace_seconds
        if (token_provider is None) == (subscription_key_provider is None):
            raise ValueError("Supply exactly one Maps credential provider.")
        self.subscription_key_provider = subscription_key_provider
        self.geocodes: dict[str, tuple[list[float], str]] = {}
        self.routes: dict[tuple[str, str], Row] = {}

    async def request(self, path: str, body: Row | None = None, **params: str) -> Row:
        for attempt in range(4):
            if self.subscription_key_provider is not None:
                headers = {"subscription-key": await self.subscription_key_provider()}
            else:
                assert self.token_provider is not None
                headers = {
                    "Authorization": f"Bearer {await self.token_provider()}",
                    "x-ms-client-id": self.client_id,
                }
            headers["Content-Type"] = "application/geo+json"
            await asyncio.sleep(self.pace_seconds)
            try:
                response = await self.http.request(
                    "GET" if body is None else "POST",
                    f"https://atlas.microsoft.com/{path}",
                    params={"api-version": API_VERSION, **params},
                    json=body,
                    headers=headers,
                )
            except httpx.RequestError:
                if attempt < 3:
                    await asyncio.sleep(2**attempt)
                    continue
                raise RuntimeError("MAPS_NETWORK_ERROR") from None
            if response.status_code in {408, 429, 500, 502, 503, 504} and attempt < 3:
                retry = response.headers.get("Retry-After", "")
                await asyncio.sleep(min(float(retry), 60) if retry.isdigit() else 2**attempt)
                continue
            if response.status_code != 200:
                # Do not expose credential-bearing request objects or arbitrary upstream bodies.
                raise RuntimeError(f"MAPS_HTTP_{response.status_code}")
            try:
                payload = response.json()
            except ValueError:
                raise RuntimeError("MAPS_INVALID_JSON") from None
            if not isinstance(payload, dict):
                raise RuntimeError("MAPS_INVALID_RESPONSE")
            return payload
        raise RuntimeError("MAPS_RETRY_EXHAUSTED")

    async def geocode(self, address: str) -> tuple[list[float], str]:
        if address not in self.geocodes:
            data = await self.request("geocode", query=address, top="1")
            try:
                feature = data["features"][0]
                props = feature["properties"]
                codes = props.get("matchCodes", [])
                if (
                    props.get("confidence") != "High"
                    or "Good" not in codes
                    or any(code in codes for code in ("Ambiguous", "UpHierarchy"))
                ):
                    raise ValueError("Geocoded address needs review.")
                points = [
                    point
                    for point in props.get("geocodePoints", [])
                    if "Route" in point.get("usageTypes", [])
                ]
                point = points[0] if points else feature
                coords = coordinate(point["geometry"]["coordinates"])
                matched = props["address"]["formattedAddress"]
                if not isinstance(matched, str) or not matched.strip():
                    raise ValueError("Missing matched address.")
            except (KeyError, IndexError, TypeError):
                raise ValueError("Azure Maps returned an incomplete geocode.") from None
            self.geocodes[address] = coords, matched
        return self.geocodes[address]

    async def route(self, origin: str, destination: str) -> Row:
        pair = origin, destination
        if pair not in self.routes:
            start, start_address = await self.geocode(origin)
            end, end_address = await self.geocode(destination)
            data = await self.request(
                "route/directions",
                body={
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {"type": "Point", "coordinates": point},
                            "properties": {"pointIndex": index, "pointType": "waypoint"},
                        }
                        for index, point in enumerate((start, end))
                    ],
                    "travelMode": "driving",
                    "optimizeRoute": "fastestWithoutTraffic",
                    "maxRouteCount": 1,
                    "routeOutputOptions": ["routePath"],
                },
            )
            try:
                paths = [
                    feature
                    for feature in data["features"]
                    if feature.get("properties", {}).get("type") == "RoutePath"
                ]
                if len(paths) != 1:
                    raise ValueError("Expected exactly one Azure Maps RoutePath.")
                path = paths[0]
                distance = finite_number(path["properties"]["distanceInMeters"], "Road meters")
                geometry = path["geometry"]
                if geometry["type"] == "LineString":
                    lines = [geometry["coordinates"]]
                elif geometry["type"] == "MultiLineString":
                    lines = geometry["coordinates"]
                else:
                    raise ValueError("Expected road LineString or MultiLineString.")
                if not lines or any(len(line) < 2 for line in lines):
                    raise ValueError("Azure Maps returned an empty road path.")
                lines = [[coordinate(point) for point in line] for line in lines]
            except (KeyError, IndexError, TypeError):
                raise ValueError("Azure Maps returned an incomplete road path.") from None
            self.routes[pair] = {
                "Driving_distance_km": distance / 1000,
                "Supplier_matched_address": start_address,
                "Plant_matched_address": end_address,
                "Supplier_route_longitude": start[0],
                "Supplier_route_latitude": start[1],
                "Plant_route_longitude": end[0],
                "Plant_route_latitude": end[1],
                "Route_geojson": json.dumps(
                    {"type": "MultiLineString", "coordinates": lines}, allow_nan=False
                ),
            }
        return self.routes[pair]

    async def enrich(
        self, rows: list[Row], carbon_price: float = 100, max_rows: int = 1000
    ) -> list[Row]:
        price = finite_number(carbon_price, "USD per tonne")
        if not 1 <= len(rows) <= max_rows:
            raise ValueError(f"Expected 1..{max_rows} deliveries.")
        ids = Counter(str(row.get("Delivery_ID") or "").strip() for row in rows)
        results = []
        for row in rows:
            out = {
                key: value
                for key, value in row.items()
                if key not in RESULT_FIELDS and "key" not in key.lower()
            }
            out.update(dict.fromkeys(RESULT_FIELDS))
            out.update(
                Carbon_price_USD_per_tonne=price,
                Refreshed_UTC=datetime.now(UTC).isoformat(),
            )
            try:
                delivery_id = str(row.get("Delivery_ID") or "").strip()
                if not delivery_id or ids[delivery_id] != 1:
                    raise ValueError("Delivery_ID must be nonempty and unique.")
                factor = finite_number(row.get("Emissions_factor_kgCO2_per_km"), "CO2 factor")
                multiplier = finite_number(row.get("Trip_multiplier"), "Trip multiplier")
                if multiplier == 0:
                    raise ValueError("Trip multiplier must be positive.")
                origin = delivery_address(row, "ManfactSupplier")
                destination = delivery_address(row, "Plant")
                out.update(Supplier_address=origin, Plant_address=destination)
                route = await self.route(origin, destination)
                co2 = finite_number(
                    route["Driving_distance_km"] * factor * multiplier, "Estimated CO2"
                )
                cost = finite_number(co2 / 1000 * price, "Carbon cost")
                out.update(route)
                out.update(
                    Emissions_factor_kgCO2_per_km=factor,
                    Trip_multiplier=multiplier,
                    CO2_emitted_kg=co2,
                    Carbon_cost_USD=cost,
                    Route_Status="OK",
                )
            except (ValueError, TypeError, RuntimeError) as error:
                out.update(
                    Route_Status="ERROR",
                    Route_Error_Reason=str(error)
                    if isinstance(error, RuntimeError)
                    else "INVALID_DATA",
                    Route_Error_Detail="Routing failed; review input or API access."
                    if isinstance(error, RuntimeError)
                    else str(error),
                )
            results.append(out)
        logger.info(
            "delivery_enrichment_completed",
            extra={
                "rows": len(results),
                "successful": sum(r["Route_Status"] == "OK" for r in results),
            },
        )
        return results


def route_points(rows: list[Row]) -> list[Row]:
    points = []
    for row in rows:
        if row["Route_Status"] != "OK":
            continue
        geometry = json.loads(row["Route_geojson"])
        for segment, line in enumerate(geometry["coordinates"]):
            for sequence, (lon, lat) in enumerate(line):
                points.append(
                    {
                        "Delivery_ID": row["Delivery_ID"],
                        "Path_ID": f"{row['Delivery_ID']}:{segment}",
                        "Route_segment": segment,
                        "Point_sequence": sequence,
                        "Longitude": lon,
                        "Latitude": lat,
                    }
                )
    return points
