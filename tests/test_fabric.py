import ast
import base64
import json
from unittest.mock import AsyncMock
from zipfile import ZipFile

import httpx
import pytest
from azure.core.credentials import AccessToken

from template_repository.fabric.client import FabricClient, definition
from template_repository.fabric.maps import DeliveryMaps, route_points
from template_repository.fabric.model import model_definition
from template_repository.fabric.notebook import build_notebook
from template_repository.fabric.report import report_definition
from template_repository.fabric.samples import csv_bytes, read_workbook


def delivery(delivery_id: str = "HOU-1") -> dict:
    return {
        "Delivery_ID": delivery_id,
        "ManfactSupplier_Street": "1500 McKinney St",
        "ManfactSupplier_City": "Houston",
        "ManfactSupplier_RegionCode": "TX",
        "ManfactSupplier_PstlCode": "77010",
        "ManfactSupplier_CtryCode": "US",
        "Plant_Street": "1001 Avenida de las Americas",
        "Plant_City": "Houston",
        "Plant_RegionCode": "TX",
        "Plant_PstlCode": "77010",
        "Plant_CtryCode": "US",
        "Emissions_factor_kgCO2_per_km": "0.27",
        "Trip_multiplier": "2",
        "Part_Qty": "999",
        "Azure_Maps_API_Key": "not-a-real-secret",
        "Distance_in_km": "0.01",
    }


def geocode_payload() -> dict:
    return {
        "features": [
            {
                "geometry": {"type": "Point", "coordinates": [-95.3, 29.7]},
                "properties": {
                    "confidence": "High",
                    "matchCodes": ["Good"],
                    "address": {"formattedAddress": "Houston TX"},
                    "geocodePoints": [
                        {
                            "usageTypes": ["Route"],
                            "geometry": {"coordinates": [-95.31, 29.71]},
                        }
                    ],
                },
            }
        ]
    }


def route_payload() -> dict:
    return {
        "features": [
            {
                "properties": {"type": "RoutePath", "distanceInMeters": 12345.6},
                "geometry": {
                    "type": "MultiLineString",
                    "coordinates": [[[-95.31, 29.71], [-95.32, 29.72]]],
                },
            }
        ]
    }


async def test_enrichment_uses_road_distance_and_caches_without_counting_parts() -> None:
    requests = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["x-ms-client-id"] == "maps-account"
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(
            200, json=geocode_payload() if request.url.path == "/geocode" else route_payload()
        )

    rows = [delivery(), {**delivery("HOU-2"), "Trip_multiplier": "1"}]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        maps = DeliveryMaps(
            http, AsyncMock(return_value="test-token"), "maps-account", pace_seconds=0
        )
        results = await maps.enrich(rows, carbon_price=100)

    assert len(requests) == 3
    assert results[0]["Driving_distance_km"] == pytest.approx(12.3456)
    assert results[0]["CO2_emitted_kg"] == pytest.approx(12.3456 * 0.27 * 2)
    assert results[0]["Carbon_cost_USD"] == pytest.approx(12.3456 * 0.27 * 2 / 1000 * 100)
    assert results[1]["CO2_emitted_kg"] == pytest.approx(results[0]["CO2_emitted_kg"] / 2)
    assert results[0]["Supplier_route_longitude"] == -95.31
    assert "Azure_Maps_API_Key" not in results[0]
    assert "not-a-real-secret" not in json.dumps(results)
    assert rows[0]["Azure_Maps_API_Key"] == "not-a-real-secret"
    points = route_points(results)
    assert len(points) == 4
    assert [point["Point_sequence"] for point in points] == [0, 1, 0, 1]
    assert points[0]["Longitude"] == -95.31


async def test_failed_refresh_clears_stale_metrics_and_does_not_use_straight_line() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403, json={"error": {"message": "do not log arbitrary upstream data"}}
        )

    row = {
        **delivery(),
        "Driving_distance_km": 10,
        "CO2_emitted_kg": 20,
        "Carbon_cost_USD": 30,
        "Supplier_route_latitude": 29.7,
        "Route_geojson": "{}",
    }
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        results = await DeliveryMaps(
            http, AsyncMock(return_value="test-token"), "maps-account", pace_seconds=0
        ).enrich([row])
    assert results[0]["Route_Error_Reason"] == "MAPS_HTTP_403"
    for field in (
        "Driving_distance_km",
        "CO2_emitted_kg",
        "Carbon_cost_USD",
        "Supplier_route_latitude",
        "Route_geojson",
    ):
        assert results[0][field] is None
    assert route_points(results) == []


async def test_key_vault_credential_is_header_only_and_never_appears_in_results() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers["subscription-key"] == "vault-test-key"
        assert "Authorization" not in request.headers
        assert "vault-test-key" not in str(request.url)
        return httpx.Response(
            200, json=geocode_payload() if request.url.path == "/geocode" else route_payload()
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        results = await DeliveryMaps(
            http,
            None,
            "maps-account",
            subscription_key_provider=AsyncMock(return_value="vault-test-key"),
            pace_seconds=0,
        ).enrich([delivery()])
    assert results[0]["Route_Status"] == "OK"
    assert "vault-test-key" not in json.dumps(results)


@pytest.mark.parametrize(
    "change",
    [
        {"Emissions_factor_kgCO2_per_km": "NaN"},
        {"Trip_multiplier": "0"},
        {"Trip_multiplier": "-1"},
        {"Plant_Street": ""},
        {"Delivery_ID": ""},
    ],
)
async def test_invalid_inputs_make_no_billable_requests(change: dict) -> None:
    token = AsyncMock(return_value="test-token")
    async with httpx.AsyncClient() as http:
        results = await DeliveryMaps(http, token, "maps-account").enrich([{**delivery(), **change}])
    token.assert_not_called()
    assert results[0]["Route_Status"] == "ERROR"
    assert results[0]["CO2_emitted_kg"] is None


async def test_duplicate_ids_and_batch_limits_are_rejected() -> None:
    token = AsyncMock()
    async with httpx.AsyncClient() as http:
        maps = DeliveryMaps(http, token, "maps-account")
        results = await maps.enrich([delivery(), delivery()])
        assert all(row["Route_Status"] == "ERROR" for row in results)
        for rows in ([], [delivery(), delivery("HOU-2")]):
            with pytest.raises(ValueError, match="Expected"):
                await maps.enrich(rows, max_rows=1)
        with pytest.raises(ValueError, match="finite"):
            await maps.enrich([delivery()], carbon_price=float("inf"))
    token.assert_not_called()


async def test_throttling_retries_but_ambiguous_geocodes_are_not_accepted(monkeypatch) -> None:
    sleep = AsyncMock()
    monkeypatch.setattr("template_repository.fabric.maps.asyncio.sleep", sleep)
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        payload = geocode_payload()
        payload["features"][0]["properties"]["matchCodes"] = ["Good", "Ambiguous"]
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        results = await DeliveryMaps(
            http, AsyncMock(return_value="token"), "maps-account", pace_seconds=0
        ).enrich([delivery()])
    assert len(calls) == 2
    assert results[0]["Route_Status"] == "ERROR"
    sleep.assert_any_await(2)


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "MultiLineString", "coordinates": []},
        {"type": "LineString", "coordinates": [[-95, 29], [-95, 91]]},
        {"type": "Point", "coordinates": [-95, 29]},
    ],
)
async def test_invalid_road_geometry_cannot_produce_carbon_metrics(geometry: dict) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        payload = geocode_payload() if request.url.path == "/geocode" else route_payload()
        if request.url.path != "/geocode":
            payload["features"][0]["geometry"] = geometry
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        results = await DeliveryMaps(
            http, AsyncMock(return_value="token"), "maps-account", pace_seconds=0
        ).enrich([delivery()])
    assert results[0]["Driving_distance_km"] is None
    assert results[0]["Carbon_cost_USD"] is None


def test_workbook_normalization_preserves_postal_codes_and_removes_credentials(tmp_path) -> None:
    path = tmp_path / "input.xlsx"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Deliveries" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships><Relationship Id="rId1" Target="/xl/worksheets/sheet1.xml"/></Relationships>',
        )
        rows = [
            ["Delivery_ID", "Plant_PstlCode", "Azure_Maps_API_Key"],
            ["HOU-1", "00123", "not-a-real-secret"],
        ]
        xml_rows = "".join(
            f'<row r="{index}">'
            + "".join(
                f'<c r="{letter}{index}" t="inlineStr"><is><t>{value}</t></is></c>'
                for letter, value in zip("ABC", values, strict=True)
            )
            + "</row>"
            for index, values in enumerate(rows, start=1)
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{xml_rows}</sheetData></worksheet>",
        )
    normalized = read_workbook(path)
    assert normalized == [{"Delivery_ID": "HOU-1", "Plant_PstlCode": "00123"}]
    assert b"not-a-real-secret" not in csv_bytes(normalized)
    with pytest.raises(ValueError, match="no 'Missing'"):
        read_workbook(path, "Missing")


async def test_fabric_long_running_operations_use_canonical_operation_id(monkeypatch) -> None:
    monkeypatch.setattr("template_repository.fabric.client.asyncio.sleep", AsyncMock())
    paths = []

    def handle(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/result"):
            return httpx.Response(200, json={"id": "new-item"})
        return httpx.Response(200, json={"status": "Succeeded"})

    credential = AsyncMock()
    credential.get_token.return_value = AccessToken("test-token", 9999999999)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        client = FabricClient(http, credential)
        result = await client.complete(
            httpx.Response(
                202,
                headers={
                    "x-ms-operation-id": "operation-id",
                    "Location": "https://regional.example/operations/operation-id",
                    "Retry-After": "0",
                },
            )
        )
        with pytest.raises(ValueError, match="Unexpected"):
            await client.request("GET", "https://untrusted.example/v1/items")
    assert result == {"id": "new-item"}
    assert paths == ["/v1/operations/operation-id", "/v1/operations/operation-id/result"]


async def test_definition_update_does_not_request_nonexistent_operation_result(monkeypatch) -> None:
    monkeypatch.setattr("template_repository.fabric.client.asyncio.sleep", AsyncMock())
    paths = []

    def handle(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, json={"status": "Succeeded"})

    credential = AsyncMock()
    credential.get_token.return_value = AccessToken("test-token", 9999999999)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        result = await FabricClient(http, credential).complete(
            httpx.Response(202, headers={"x-ms-operation-id": "update-id", "Retry-After": "0"}),
            has_result=False,
        )
    assert result == {}
    assert paths == ["/v1/operations/update-id"]


def decoded(item: dict) -> dict:
    return {part["path"]: json.loads(base64.b64decode(part["payload"])) for part in item["parts"]}


def test_report_references_match_semantic_model_and_notebook_compiles() -> None:
    model = decoded(model_definition("server.example"))["model.bim"]["model"]
    fields = {
        table["name"]: {
            entry["name"] for key in ("columns", "measures") for entry in table.get(key, [])
        }
        for table in model["tables"]
    }
    report = decoded(report_definition("test-model-id"))
    for path, content in report.items():
        if not path.endswith("/visual.json"):
            continue
        for role in content["visual"]["query"]["queryState"].values():
            for entry in role["projections"]:
                field = next(iter(entry["field"].values()))
                assert field["Property"] in fields[field["Expression"]["SourceRef"]["Entity"]]
    notebook = build_notebook(
        "workspace",
        "lakehouse",
        "maps-client",
        100.0,
        "https://example.vault.azure.net/",
        "maps-key",
    )
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            compile(
                "".join(cell["source"]), "<notebook>", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
            )
    assert all(not cell.get("outputs") for cell in notebook["cells"])
    assert decoded(definition({"sample.json": json.dumps({"ok": True})}))["sample.json"]["ok"]
