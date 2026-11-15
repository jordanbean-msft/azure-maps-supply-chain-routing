import ast
import csv
import inspect
import io
import json
import runpy
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "fabric" / "notebooks" / "Refresh_delivery_carbon.ipynb"
FABRIC_SOURCE = ROOT / "src" / "template_repository" / "fabric"


@pytest.fixture
def notebook() -> dict[str, Any]:
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


@pytest.fixture
def helpers(notebook: dict[str, Any]) -> dict[str, Any]:
    namespace: dict[str, Any] = {}
    for cell in notebook["cells"]:
        if "parameters" in cell["metadata"].get("tags", []):
            break
        if cell["cell_type"] != "code":
            continue
        tree = ast.parse("".join(cell["source"]))
        # Fabric-only imports are supplied by fakes in the execution test below.
        tree.body = [
            node
            for node in tree.body
            if not (
                (
                    isinstance(node, ast.Import)
                    and any(alias.name == "notebookutils" for alias in node.names)
                )
                or (isinstance(node, ast.ImportFrom) and (node.module or "").startswith("pyspark"))
            )
        ]
        exec(compile(tree, str(NOTEBOOK), "exec"), namespace)
    return namespace


def delivery(delivery_id: str = "HOU-1") -> dict[str, Any]:
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
        "Azure_Maps_API_Key": "test-key-not-for-export",
        "Driving_distance_km": 999,
        "CO2_emitted_kg": 999,
    }


def maps_response(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/geocode":
        supplier = request.url.params["query"].startswith("1500")
        coords = [-95.31, 29.71] if supplier else [-95.32, 29.72]
        payload = {
            "features": [
                {
                    "geometry": {"type": "Point", "coordinates": coords},
                    "properties": {
                        "confidence": "High",
                        "matchCodes": ["Good"],
                        "address": {"formattedAddress": request.url.params["query"]},
                    },
                }
            ]
        }
    else:
        payload = {
            "features": [
                {
                    "properties": {"type": "RoutePath", "distanceInMeters": 12345.6},
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-95.31, 29.71], [-95.32, 29.72]],
                    },
                }
            ]
        }
    return httpx.Response(200, json=payload)


async def test_stages_preserve_snapshots_cache_and_match_original(
    helpers: dict[str, Any],
) -> None:
    rows = [delivery(), delivery("HOU-2"), delivery("HOU-3")]
    for suffix in helpers["ADDRESS_FIELDS"]:
        rows[2][f"ManfactSupplier_{suffix}"], rows[2][f"Plant_{suffix}"] = (
            rows[2][f"Plant_{suffix}"],
            rows[2][f"ManfactSupplier_{suffix}"],
        )
    original_rows = deepcopy(rows)
    requests = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["subscription-key"] == "test-key"
        assert request.url.params["api-version"] == "2025-01-01"
        if request.method == "POST":
            body = json.loads(request.content)
            assert body["travelMode"] == "driving"
            assert body["optimizeRoute"] == "fastestWithoutTraffic"
            expected_start = [-95.31, 29.71] if len(requests) == 3 else [-95.32, 29.72]
            assert body["features"][0]["geometry"]["coordinates"] == expected_start
        return maps_response(request)

    validated = helpers["validate_deliveries"](rows, 100, 1000)
    assert not requests
    assert all(row["Driving_distance_km"] is None for row in validated)
    with pytest.raises(ValueError, match="Expected ROUTED"):
        helpers["calculate_carbon"](validated)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        client = helpers["MapsHttpClient"](
            http,
            None,
            "maps-client",
            subscription_key_provider=AsyncMock(return_value="test-key"),
            pace_seconds=0,
        )
        with pytest.raises(ValueError, match="Expected GEOCODED"):
            await helpers["route_deliveries"](validated, client)
        assert not requests
        geocoded = await helpers["geocode_deliveries"](validated, client)
        assert [request.url.path for request in requests] == ["/geocode", "/geocode"]
        assert all(row["Driving_distance_km"] is None for row in geocoded)
        routed = await helpers["route_deliveries"](geocoded, client)
    assert [request.url.path for request in requests[2:]] == [
        "/route/directions",
        "/route/directions",
    ]
    assert all(row["CO2_emitted_kg"] is None for row in routed)
    enriched = helpers["calculate_carbon"](routed)
    assert len(requests) == 4
    assert rows == original_rows
    for snapshot, status in (
        (validated, "VALIDATED"),
        (geocoded, "GEOCODED"),
        (routed, "ROUTED"),
        (enriched, "OK"),
    ):
        assert all(row["Route_Status"] == status for row in snapshot)

    baseline = runpy.run_path(str(FABRIC_SOURCE / "maps.py"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(maps_response)) as http:
        expected = await baseline["DeliveryMaps"](
            http,
            None,
            "maps-client",
            subscription_key_provider=AsyncMock(return_value="test-key"),
            pace_seconds=0,
        ).enrich(rows)
    for actual_row, expected_row in zip(enriched, expected, strict=True):
        assert {k: v for k, v in actual_row.items() if k != "Refreshed_UTC"} == {
            k: v for k, v in expected_row.items() if k != "Refreshed_UTC"
        }
    assert helpers["route_points"](enriched) == baseline["route_points"](expected)
    async with httpx.AsyncClient(transport=httpx.MockTransport(maps_response)) as http:
        client = helpers["MapsHttpClient"](
            http,
            None,
            "maps-client",
            subscription_key_provider=AsyncMock(return_value="test-key"),
            pace_seconds=0,
        )
        updated = deepcopy(validated)
        updated[0]["Supplier_address"] = updated[0]["Plant_address"]
        rerun = await helpers["geocode_deliveries"](updated, client)
    assert rerun[0]["Supplier_route_longitude"] == -95.32
    assert geocoded[0]["Supplier_route_longitude"] == -95.31


@pytest.mark.parametrize(
    "failure", ["invalid", "duplicate", "ambiguous", "http", "geometry", "overflow"]
)
async def test_failed_rows_remain_errors_through_stages(
    helpers: dict[str, Any], failure: str
) -> None:
    rows = [delivery()]
    if failure == "invalid":
        rows[0]["Trip_multiplier"] = "0"
    elif failure == "duplicate":
        rows.append(delivery())
    elif failure == "overflow":
        rows[0].update(Emissions_factor_kgCO2_per_km="1e308", Trip_multiplier="1e308")
    requests = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if failure == "http" and request.url.path != "/geocode":
            return httpx.Response(403, json={"error": {"message": "never export this body"}})
        response = maps_response(request)
        payload = response.json()
        if failure == "ambiguous" and request.url.path == "/geocode":
            payload["features"][0]["properties"]["matchCodes"] = ["Ambiguous"]
        elif failure == "geometry" and request.url.path != "/geocode":
            payload["features"][0]["geometry"]["coordinates"] = []
        return httpx.Response(200, json=payload)

    validated = helpers["validate_deliveries"](rows)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        client = helpers["MapsHttpClient"](
            http,
            None,
            "",
            subscription_key_provider=AsyncMock(return_value="test-key"),
            pace_seconds=0,
        )
        geocoded = await helpers["geocode_deliveries"](validated, client)
        routed = await helpers["route_deliveries"](geocoded, client)
    enriched = helpers["calculate_carbon"](routed)
    for row in enriched:
        assert row["Route_Status"] == "ERROR"
        assert row["Route_Error_Reason"] == (
            "MAPS_HTTP_403" if failure == "http" else "INVALID_DATA"
        )
        assert all(
            row[field] is None
            for field in (
                "Driving_distance_km",
                "CO2_emitted_kg",
                "Carbon_cost_USD",
                "Route_geojson",
                "Supplier_route_latitude",
                "Plant_route_longitude",
            )
        )
    if failure in {"invalid", "duplicate"}:
        assert not requests
    assert helpers["route_points"](enriched) == []
    assert "test-key" not in json.dumps(enriched)
    assert "never export" not in json.dumps(enriched)


@pytest.mark.parametrize("rows", [[], [delivery()]])
def test_print_stage_shows_rows_without_keys_or_mutating_inputs(
    helpers: dict[str, Any], rows: list[dict[str, Any]], capsys: pytest.CaptureFixture[str]
) -> None:
    original = deepcopy(rows)

    helpers["print_stage"]("input", rows)

    output = capsys.readouterr().out
    data = json.loads(output)
    assert data["stage"] == "input"
    assert data["row_count"] == len(rows)
    assert data["rows"] == [
        {key: value for key, value in row.items() if "key" not in key.lower()} for row in rows
    ]
    assert "test-key-not-for-export" not in output
    assert rows == original


async def test_numbered_cells_execute_and_save_with_fake_fabric(
    notebook: dict[str, Any], helpers: dict[str, Any]
) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=delivery().keys())
    writer.writeheader()
    writer.writerows([delivery(), {**delivery("INVALID"), "Trip_multiplier": "0"}])
    spark = MagicMock()
    writes = []
    for _ in range(2):
        frame = MagicMock()
        frame.write.format.return_value = frame.write
        frame.write.mode.return_value = frame.write
        frame.write.option.return_value = frame.write
        writes.append(frame)
    spark.createDataFrame.side_effect = writes
    fs = SimpleNamespace(
        ls=lambda _: [SimpleNamespace(name="workbook_deliveries.csv", size=len(buffer.getvalue()))],
        head=lambda *_: buffer.getvalue(),
        put=MagicMock(),
    )
    real_async_client = httpx.AsyncClient
    printed = MagicMock()
    helpers.update(
        print=printed,
        notebookutils=SimpleNamespace(
            fs=fs, credentials=SimpleNamespace(getSecret=MagicMock(return_value="test-key"))
        ),
        SparkSession=SimpleNamespace(builder=SimpleNamespace(getOrCreate=lambda: spark)),
        StructType=lambda fields: fields,
        StructField=lambda *args: args,
        DoubleType=lambda: "double",
        LongType=lambda: "long",
        StringType=lambda: "string",
        httpx=SimpleNamespace(
            AsyncClient=lambda **kwargs: real_async_client(
                **kwargs, transport=httpx.MockTransport(maps_response)
            ),
            RequestError=httpx.RequestError,
        ),
    )
    running = False
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        if "parameters" in cell["metadata"].get("tags", []):
            running = True
        if not running:
            continue
        code = compile(
            "".join(cell["source"]), str(NOTEBOOK), "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
        )
        result = eval(code, helpers)
        if inspect.isawaitable(result):
            await result
    assert [row["Route_Status"] for row in helpers["enriched"]] == ["OK", "ERROR"]
    assert helpers["summary"]["successful"] == 1
    assert helpers["summary"]["co2_kg"] == pytest.approx(6.666624)
    writes[0].write.saveAsTable.assert_called_once_with("deliveries")
    writes[1].write.saveAsTable.assert_called_once_with("route_points")
    exports = {call.args[0]: json.loads(call.args[1]) for call in fs.put.call_args_list}
    assert len(exports["Files/sample/routes.geojson"]["features"]) == 1
    assert exports["Files/sample/refresh_summary.json"] == helpers["summary"]
    output = [json.loads(call.args[0]) for call in printed.call_args_list]
    snapshots = {item["stage"]: item for item in output[:-1]}
    for stage, variable in (
        ("input", "deliveries"),
        ("validated", "validated"),
        ("geocoded", "geocoded"),
        ("routed", "routed"),
        ("enriched", "enriched"),
        ("typed", "typed"),
        ("saved_deliveries", "typed"),
        ("saved_route_points", "points"),
        ("exported_routes", "features"),
    ):
        expected = [
            {key: value for key, value in row.items() if "key" not in key.lower()}
            for row in helpers[variable]
        ]
        assert snapshots[stage]["rows"] == expected
        assert snapshots[stage]["row_count"] == len(expected)
    assert snapshots["validated"]["statuses"] == {"VALIDATED": 1, "ERROR": 1}
    assert snapshots["enriched"]["statuses"] == {"OK": 1, "ERROR": 1}
    assert output[-1] == helpers["summary"]
    assert "test-key" not in json.dumps(output)


def test_factory_preserves_stages_and_updates_parameters(
    notebook: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    template = tmp_path / "fabric" / "notebooks" / NOTEBOOK.name
    template.parent.mkdir(parents=True)
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            cell.update(execution_count=7, outputs=[{"output_type": "stream", "text": "old"}])
    template.write_text(json.dumps(notebook), encoding="utf-8")
    build = runpy.run_path(str(FABRIC_SOURCE / "notebook.py"))["build_notebook"]
    generated = build(
        "new-workspace", "new-lakehouse", "new-client", 75.0, "test-vault", "test-secret"
    )
    assert len(generated["cells"]) == len(notebook["cells"])
    for actual, expected in zip(generated["cells"], notebook["cells"], strict=True):
        if actual["cell_type"] == "code":
            assert actual["outputs"] == []
            assert actual["execution_count"] is None
        if "parameters" not in actual["metadata"].get("tags", []):
            assert actual["source"] == expected["source"]
        else:
            params: dict[str, Any] = {}
            exec("".join(actual["source"]), params)
            assert params["CARBON_PRICE_USD_PER_TONNE"] == 75.0
            assert params["MAPS_CLIENT_ID"] == "new-client"
    lakehouse = generated["metadata"]["dependencies"]["lakehouse"]
    assert lakehouse["default_lakehouse"] == "new-lakehouse"
    assert lakehouse["default_lakehouse_workspace_id"] == "new-workspace"
    notebook["cells"].append(
        deepcopy(
            next(
                cell
                for cell in notebook["cells"]
                if "parameters" in cell["metadata"].get("tags", [])
            )
        )
    )
    template.write_text(json.dumps(notebook), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one parameters"):
        build("w", "l", "c", 100, "v", "s")
