"""Houston delivery road distance and CO2; Python 3 standard library only.

Azure Maps APIs: Geocode and Route Directions, version 2025-01-01.
One row represents one vehicle trip. The 0.270 kg CO2/vehicle-km demo factor
is illustrative, not certified. Road distance is supplier -> plant, one-way,
fastestWithoutTraffic, driving mode (not restricted commercial-truck routing).

Data flow:
    delivery address columns -> GET /geocode -> routable [longitude, latitude]
    -> POST /route/directions -> RoutePath.distanceInMeters -> driving km
    -> driving km * emissions factor * trip multiplier -> kg CO2.

Distance_in_km is the separate straight-line comparison, never a road-distance
fallback. Failed rows retain null driving distance/CO2 and include an error code
and readable detail. Part quantities and weights do not enter this vehicle-km
emissions model; consolidate multiple part rows belonging to one physical trip.

Standalone usage:
    python houston_delivery_co2.py
    python houston_delivery_co2.py --input deliveries.csv --output results.csv
The key comes from AZURE_MAPS_API_KEY, a hidden terminal prompt, or an input
Azure_Maps_API_Key column. The Synapse notebook retrieves its default key from
Key Vault or the environment before calling process_deliveries().

API contracts:
    https://learn.microsoft.com/en-us/rest/api/maps/search/get-geocoding?view=rest-maps-2025-01-01
    https://learn.microsoft.com/en-us/rest/api/maps/route/post-route-directions?view=rest-maps-2025-01-01
"""

import argparse
import csv
import getpass
import json
import math
import os
import time
from collections import Counter
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class MapsError(RuntimeError):
    """Keep a machine-readable reason separate from the human-readable detail."""

    def __init__(self, reason, message):
        super().__init__(message)
        self.reason = reason


def redact(message, key):
    """Remove this request's key, including its URL-encoded form, from errors."""
    return str(message).replace(key, "[redacted]").replace(
        quote(key, safe=""), "[redacted]"
    ) if key else str(message)


def number(value, name):
    """Accept numeric CSV strings but reject NaN/infinity before API/JSON use."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number.") from None
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite.")
    return result


def address(row, supplier=False):
    """Build the geocoding query from street, city, state, postal code and country.

    Example: "1500 McKinney St, Houston, TX, 77010, US".
    Supplier is the route origin; the plant is the destination. Reference
    latitude/longitude columns are deliberately not used to resolve the route.
    """
    fields = (
        ["ManfactSupplier_Street", "ManfactSupplier_City", "ManfactSupplier_RegionCode",
         "ManfactSupplier_PstlCode", "ManfactSupplier_CtryCode"]
        if supplier else
        ["Plant_Street", "Plant_City", "Plant_RegionCode", "Plant_PstlCode", "Plant_CtryCode"]
    )
    values = [" ".join(str(row.get(f) or "").split()) for f in fields]
    missing = [f for f, value in zip(fields, values) if not value]
    if missing:
        raise ValueError("Missing address fields: " + ", ".join(missing))
    return ", ".join(values)


def haversine_km(row):
    """Calculate the old straight-line metric, using Earth's mean radius in km.

    If reference coordinates are absent, retain an existing Distance_in_km
    value or leave it null. Routing still requires the address columns; this
    comparison metric is never substituted for an Azure Maps road distance.
    """
    fields = ["Plant_Latitude", "Plant_Longitude",
              "ManfactSupplier_Latitude", "ManfactSupplier_Longitude"]
    if not all(row.get(f) not in (None, "") for f in fields):
        value = row.get("Distance_in_km")
        return None if value in (None, "") else number(value, "Distance_in_km")
    lat1, lon1, lat2, lon2 = [number(row[f], f) for f in fields]
    if abs(lat1) > 90 or abs(lat2) > 90 or abs(lon1) > 180 or abs(lon2) > 180:
        raise ValueError("Reference latitude/longitude is out of range.")
    a = (math.sin(math.radians(lat2 - lat1) / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    # Clamp floating-point roundoff to the domain accepted by sqrt/asin.
    return 2 * 6371 * math.asin(math.sqrt(min(1, max(0, a))))


class AzureMaps:
    """One credential plus per-run geocode/route caches, kept only in memory."""

    def __init__(self, key):
        self.key = key
        self.geocodes = {}
        self.routes = {}

    def request(self, path, body=None, **parameters):
        """Send an authenticated GET or POST and return the decoded JSON object.

        GET /geocode?api-version=2025-01-01&query=<encoded-address>&top=1
        POST /route/directions?api-version=2025-01-01
            Body: GeoJSON FeatureCollection plus routing options (see route()).
        Both requests send subscription-key in an HTTPS header, not in the URL.

        Successful responses are JSON objects containing a features array.
        HTTP failures may contain {"error": {"code": "...", "message": "..."}}.
        Some errors are HTML/plain text instead; retain their HTTP status/reason.
        No credential-bearing request headers or full error bodies are printed.
        """
        # URL-encode commas, spaces and other address characters instead of
        # concatenating unescaped address text into the query string.
        url = "https://atlas.microsoft.com/" + path + "?" + urlencode(
            {"api-version": "2025-01-01", **parameters}
        )
        # urllib chooses GET when data is None and POST when JSON bytes are present.
        # allow_nan=False prevents nonstandard JSON numeric values leaving the driver.
        data = None if body is None else json.dumps(body, allow_nan=False).encode()
        request = Request(url, data=data, headers={
            "subscription-key": self.key,
            "Content-Type": "application/geo+json",
            "Accept": "application/json",
        })
        # Four total attempts = the initial request plus at most three retries.
        for attempt in range(4):
            # Basic sequential pacing, not a guarantee of any account's quota limits.
            time.sleep(0.25)
            try:
                # Network operations have a timeout; json.load decodes the response
                # body, not the HTTP headers or an Excel/Power Query wrapper.
                with urlopen(request, timeout=60) as response:
                    payload = json.load(response)
                if not isinstance(payload, dict):
                    raise MapsError("INVALID_RESPONSE", f"{path}: expected a JSON object.")
                return payload
            except HTTPError as exc:
                # Retry only throttling/timeouts/transient server failures.
                # Invalid keys, denied permissions and bad inputs need correction,
                # so HTTP 400/401/403 are not retried.
                if exc.code in (408, 429, 500, 502, 503, 504) and attempt < 3:
                    retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
                    # Honor numeric Retry-After seconds up to 60; an HTTP-date or
                    # absent header uses exponential waits of 2, 4 and 8 seconds.
                    delay = min(60, float(retry_after)) if retry_after.isdigit() else 2 ** (attempt + 1)
                    exc.close()
                    time.sleep(delay)
                    continue
                # Bound error-body reading to 64 KiB; never dump it wholesale.
                raw = exc.read(65536)
                exc.close()
                try:
                    payload = json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    # An HTML/non-JSON failure still gets a useful HTTP diagnostic.
                    payload = {}
                detail = payload.get("error", payload) if isinstance(payload, dict) else {}
                code = detail.get("code", "") if isinstance(detail, dict) else ""
                message = detail.get("message", "") if isinstance(detail, dict) else ""
                hint = (" Check the Azure Maps key and whether shared-key authentication is permitted."
                        if exc.code in (401, 403) else "")
                raise MapsError(
                    f"HTTP_{exc.code}",
                    redact(f"{path}: HTTP {exc.code} {code}: {message or exc.reason}.{hint}", self.key),
                ) from None
            except (URLError, TimeoutError) as exc:
                raise MapsError("NETWORK_ERROR", redact(f"{path}: {exc}", self.key)) from None
            except (ValueError, UnicodeDecodeError) as exc:
                raise MapsError("INVALID_JSON", redact(f"{path}: {exc}", self.key)) from None

    def geocode(self, location):
        """Resolve an address to a routable GeoJSON point and matched address.

        Relevant fields in an illustrative GET /geocode response:
            {
                "features": [{
                    "properties": {
                        "confidence": "High",
                        "matchCodes": ["Good"],
                        "address": {"formattedAddress": "<matched address>"},
                        "geocodePoints": [{
                            "usageTypes": ["Route"],
                            "geometry": {
                                "coordinates": [-95.4, 29.7]
                            }
                        }]
                    }
                }]
            }
        The example coordinates explain the schema; they are not API results.
        GeoJSON always orders coordinates [longitude, latitude], not lat/lon.
        """
        if location not in self.geocodes:
            # top=1 requests the best candidate; confidence/matchCodes below still
            # reject a vague or ambiguous result rather than silently accepting it.
            data = self.request("geocode", query=location, top=1)
            features = data.get("features")
            if not isinstance(features, list) or not features or not isinstance(features[0], dict):
                raise MapsError("GEOCODE_NO_MATCH", f"No address match: {location}")
            feature = features[0]
            props = feature.get("properties") or {}
            codes = props.get("matchCodes") or []
            if (props.get("confidence") != "High" or "Good" not in codes
                    or "Ambiguous" in codes or "UpHierarchy" in codes):
                raise MapsError("GEOCODE_REVIEW", f"Address needs review: {location}")
            # Prefer a road-access/routing point over a building's display point.
            # Fall back to the feature geometry only if no Route point is supplied.
            points = [p for p in (props.get("geocodePoints") or [])
                      if "Route" in (p.get("usageTypes") or [])]
            point = points[0] if points else feature
            coords = (point.get("geometry") or {}).get("coordinates")
            matched = (props.get("address") or {}).get("formattedAddress")
            if not isinstance(coords, list) or len(coords) != 2 or not matched:
                raise MapsError("GEOCODE_INVALID", f"Missing address/coordinates: {location}")
            try:
                lon, lat = [number(value, "Geocoded coordinate") for value in coords]
            except ValueError as exc:
                raise MapsError("GEOCODE_INVALID", str(exc)) from None
            if abs(lon) > 180 or abs(lat) > 90:
                raise MapsError("GEOCODE_INVALID", f"Coordinates out of range: {location}")
            # Cache successful matches only. Repeated plants/suppliers reuse them
            # during this run, reducing latency and billable geocoding calls.
            self.geocodes[location] = ([lon, lat], matched)
        return self.geocodes[location]

    def route(self, origin, destination):
        """Request one supplier-to-plant road route, returning km and audit fields.

        POST body:
            type="FeatureCollection"; features contains two Point features.
            pointIndex=0 is the supplier; pointIndex=1 is the plant.
            Each pointType="waypoint"; geometry.coordinates is [lon, lat].

        Relevant fields in an illustrative successful response:
            {
                "features": [{
                    "properties": {
                        "type": "RoutePath",
                        "distanceInMeters": 12345.6
                    }
                }]
            }
        Here 12345.6 is a schema example, not a measured Houston route.
        Its conversion is 12.3456 km. Other features can describe waypoints or
        instructions; they must not be summed into the whole-route distance.
        """
        # This cache is directional: A -> B and B -> A are different routes.
        # Rerunning process_deliveries starts fresh caches and new API requests.
        pair = (origin, destination)
        if pair not in self.routes:
            start, start_address = self.geocode(origin)
            end, end_address = self.geocode(destination)
            body = {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "geometry": {"type": "Point", "coordinates": point},
                     "properties": {"pointIndex": i, "pointType": "waypoint"}}
                    for i, point in enumerate((start, end))
                ],
                # Light-vehicle road routing, not straight-line measurement.
                # Commercial-truck restrictions require different routing options.
                "travelMode": "driving",
                # Choose a fastest road route without using current traffic.
                # This is not a request for the shortest possible road distance.
                "optimizeRoute": "fastestWithoutTraffic",
                "maxRouteCount": 1,
                "routeOutputOptions": ["routePath"],
            }
            data = self.request("route/directions", body=body)
            # Select the complete RoutePath feature, not individual route legs.
            paths = [f for f in (data.get("features") or [])
                     if (f.get("properties") or {}).get("type") == "RoutePath"]
            if len(paths) != 1:
                raise MapsError("ROUTE_NOT_FOUND", "Expected one usable RoutePath.")
            try:
                meters = number(paths[0]["properties"].get("distanceInMeters"), "Road distance")
            except ValueError as exc:
                raise MapsError("ROUTE_INVALID", str(exc)) from None
            if meters < 0:
                raise MapsError("ROUTE_INVALID", "Road distance cannot be negative.")
            self.routes[pair] = {
                # Keep full precision; round only for presentation, not before CO2.
                "Driving_distance_km": meters / 1000,
                "Supplier_matched_address": start_address, "Plant_matched_address": end_address,
                "Supplier_route_latitude": start[1], "Supplier_route_longitude": start[0],
                "Plant_route_latitude": end[1], "Plant_route_longitude": end[0],
            }
        return self.routes[pair]


def process_deliveries(rows, api_key="", max_rows=1000):
    """Enrich delivery dictionaries; return new dictionaries without API keys.

    rows: input dictionaries with the spreadsheet's address/factor columns.
    api_key: default key from Key Vault/environment; a nonempty per-row key wins.
    max_rows: small-batch guardrail, not an API quota or Spark partition size.

    Output preserves input business columns and appends route audit/error
    fields, driving distance and a final CO2_emitted_kg column. Failed rows have
    null driving distance/CO2 plus Route_Error_Reason and Route_Error_Detail.
    A valid zero-length route, unlike a failed route, can legitimately yield 0.

    Run on the Synapse driver, never inside Spark UDFs/mapPartitions: task
    retries/speculative execution could repeat billable HTTP calls, and
    captured keys could otherwise be serialized to Spark workers.
    """
    rows = list(rows)
    if not rows or len(rows) > max_rows:
        raise ValueError(f"Supply between 1 and {max_rows} deliveries; partition larger batches.")
    # Duplicate delivery IDs are ambiguous; flag them rather than counting a
    # repeated row as an additional physical shipment without an explicit ID.
    ids = Counter(str(r.get("Delivery_ID") or "").strip() for r in rows)
    clients, results = {}, []
    derived = {
        "Azure_Maps_API_Key", "Route_Status", "Driving_distance_km", "CO2_emitted_kg",
        "Supplier_matched_address", "Plant_matched_address", "Supplier_route_latitude",
        "Supplier_route_longitude", "Plant_route_latitude", "Plant_route_longitude",
        "Refreshed_UTC", "Route_Error_Reason", "Route_Error_Detail", "Input_signature",
        "Supplier_address", "Plant_address",
    }
    for row in rows:
        # Drop both secrets and any previously calculated route fields before
        # enrichment, so failed refreshes cannot accidentally reuse stale results.
        out = {k: v for k, v in row.items() if k not in derived}
        out.update({
            "Route_Status": None, "Supplier_address": None, "Plant_address": None,
            "Supplier_matched_address": None, "Plant_matched_address": None,
            "Supplier_route_latitude": None, "Supplier_route_longitude": None,
            "Plant_route_latitude": None, "Plant_route_longitude": None,
            "Refreshed_UTC": datetime.now(timezone.utc).isoformat(),
            "Route_Error_Reason": None, "Route_Error_Detail": None,
            "Driving_distance_km": None, "CO2_emitted_kg": None,
        })
        # Keep key selection local; neither the key column nor the default key
        # is copied into output dictionaries or the resulting Spark DataFrame.
        key = str(row.get("Azure_Maps_API_Key") or api_key or "").strip()
        try:
            delivery_id = str(row.get("Delivery_ID") or "").strip()
            if not delivery_id or ids[delivery_id] != 1:
                raise ValueError("Delivery_ID must be nonempty and unique.")
            factor = number(row.get("Emissions_factor_kgCO2_per_km"), "Emissions factor")
            multiplier = number(row.get("Trip_multiplier"), "Trip multiplier")
            if factor < 0 or multiplier <= 0:
                raise ValueError("Emissions factor must be >= 0; trip multiplier must be > 0.")
            origin, destination = address(row, True), address(row)
            out["Supplier_address"], out["Plant_address"] = origin, destination
            # Retain the spreadsheet's straight-line comparison independently.
            out["Distance_in_km"] = haversine_km(row)
            out["Emissions_factor_kgCO2_per_km"], out["Trip_multiplier"] = factor, multiplier
            if not key:
                raise MapsError("MISSING_API_KEY", "Supply an Azure Maps key via Key Vault, environment or input column.")
            if key not in clients:
                # Each key has separate caches, preventing cross-account reuse.
                clients[key] = AzureMaps(key)
            route = clients[key].route(origin, destination)
            # Units: km * (kg CO2 / vehicle-km) * number of equivalent legs.
            # Do NOT multiply by part quantity or part weight in this trip model.
            # multiplier=2 approximates a same-distance return; use a reversed
            # address row if an actual reverse-road route is required.
            co2 = route["Driving_distance_km"] * factor * multiplier
            if not math.isfinite(co2):
                raise ValueError("Calculated CO2 exceeds the supported numeric range.")
            out.update(route)
            out["CO2_emitted_kg"] = co2
            out["Route_Status"] = "OK"
        except (MapsError, ValueError) as exc:
            # Expected API/input failures are row-level diagnostics. Unexpected
            # programming errors still propagate rather than being hidden.
            reason = exc.reason if isinstance(exc, MapsError) else "INVALID_INPUT"
            out["Route_Status"] = "ERROR: " + reason
            out["Route_Error_Reason"] = reason
            out["Route_Error_Detail"] = redact(str(exc), key)
        # Reinsert to keep CO2 last even if an input omitted optional columns.
        out["CO2_emitted_kg"] = out.pop("CO2_emitted_kg")
        results.append(out)
    return results


def houston_sample():
    """Build 24 fictitious deliveries, with 12 unique directed address pairs.

    Public landmark addresses make the demo geocodable; names do not describe
    the real occupants or imply supplier relationships. Approximate coordinates
    are for the Haversine comparison only. The API resolves the actual route
    coordinates afresh from addresses. Duplicate address pairs are deliberate:
    they demonstrate caching while retaining distinct Delivery_ID values.
    """
    plants = [
        ("HOU01", "Bayou Assembly (DUMMY)", "77010", "1001 Avenida de las Americas", 29.7520, -95.3578),
        ("HOU02", "South Houston Works (DUMMY)", "77054", "1 NRG Pkwy", 29.6847, -95.4107),
        ("HOU03", "Medical Center Assembly (DUMMY)", "77030", "7000 Fannin St", 29.7048, -95.4025),
    ]
    suppliers = [
        ("SUP001", "Bayou Fasteners (DUMMY)", "77010", "1500 McKinney St", 29.7535, -95.3592),
        ("SUP002", "Memorial Components (DUMMY)", "77007", "1400 Memorial Dr", 29.7624, -95.3869),
        ("SUP003", "Buffalo Bayou Parts (DUMMY)", "77002", "410 Bagby St", 29.7643, -95.3678),
        ("SUP004", "Hermann Industrial (DUMMY)", "77030", "5555 Hermann Park Dr", 29.7221, -95.3896),
        ("SUP005", "Downtown Packaging (DUMMY)", "77002", "1510 Polk St", 29.7508, -95.3621),
        ("SUP006", "Crawford Logistics (DUMMY)", "77002", "501 Crawford St", 29.7573, -95.3555),
        ("SUP007", "Uptown Plastics (DUMMY)", "77056", "2800 Post Oak Blvd", 29.7371, -95.4617),
        ("SUP008", "West Loop Metals (DUMMY)", "77027", "2400 W Loop S", 29.7413, -95.4576),
    ]
    rows = []
    for i in range(24):
        plant, supplier = plants[(i % 12) // 4], suppliers[(i % 12) % 8]
        rows.append({
            "Delivery_ID": f"HOU-{i + 1:04d}", "PlantCode": plant[0], "PlantName": plant[1],
            "Plant_CtryCode": "US", "Plant_Ctry": "United States", "Plant_City": "Houston",
            "Plant_PstlCode": plant[2], "Plant_Street": plant[3], "Plant_RegionCode": "TX",
            "Plant_Latitude": plant[4], "Plant_Longitude": plant[5],
            "Part_Qty": 450 + i * 75, "Part_UOM": "EA",
            "Part_NetWeight_kg": round(0.045 + (i % 6) * 0.031, 3), "WeightUnit": "KG",
            "ManfactSupplier_ID": supplier[0], "ManfactSupplier_Name": supplier[1],
            "ManfactSupplier_CtryCode": "US", "ManfactSupplier_Ctry": "United States",
            "ManfactSupplier_PstlCode": supplier[2], "ManfactSupplier_Street": supplier[3],
            "ManfactSupplier_RegionCode": "TX", "ManfactSupplier_City": "Houston",
            "ManfactSupplier_Latitude": supplier[4], "ManfactSupplier_Longitude": supplier[5],
            "Distance_in_km": None, "Azure_Maps_API_Key": "",
            "Emissions_factor_kgCO2_per_km": 0.270, "Trip_multiplier": 1,
        })
    return rows


# Standalone entry point; the notebook embeds only the definitions above.
def main():
    """Read an optional local CSV, enrich deliveries and write a new result CSV.

    Synapse uses the notebook's cells instead of this terminal entry point:
    ADLS reads/writes and Key Vault retrieval belong to its Spark environment.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Local CSV input; omit for 24 dummy Houston deliveries.")
    parser.add_argument("--output", default="houston_delivery_results.csv")
    args = parser.parse_args()
    if args.input:
        # utf-8-sig accepts Excel-exported UTF-8 CSVs with a BOM. DictReader keeps
        # postal codes/IDs as text, preserving any significant leading zeros.
        with open(args.input, encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
    else:
        rows = houston_sample()
    key = os.environ.get("AZURE_MAPS_API_KEY", "").strip()
    if not key and any(not str(row.get("Azure_Maps_API_Key") or "").strip() for row in rows):
        # The terminal hides typed characters; never place the key in CLI arguments
        # or print it, where shell history/process listings could expose it.
        key = getpass.getpass("Azure Maps API key (hidden; not saved): ").strip()
    results = process_deliveries(rows, key)
    # Exclusive creation refuses to overwrite an existing output file.
    # The result dictionaries already exclude Azure_Maps_API_Key.
    with open(args.output, "x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(k for r in results for k in r)))
        writer.writeheader()
        writer.writerows(results)
    print(f"Saved {len(results)} deliveries to {args.output}. Statuses: {dict(Counter(r['Route_Status'] for r in results))}")


if __name__ == "__main__":
    main()
