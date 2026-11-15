import argparse
import asyncio
import base64
import json
import logging
import math
from pathlib import Path
from typing import Any

import httpx
from azure.identity.aio import AzureCliCredential

from template_repository.fabric.client import FabricClient, definition
from template_repository.fabric.model import model_definition
from template_repository.fabric.notebook import build_notebook
from template_repository.fabric.report import report_definition
from template_repository.fabric.samples import csv_bytes, read_csv, read_workbook
from template_repository.fabric.settings import FabricSettings

logger = logging.getLogger(__name__)
NOTEBOOK_NAME = "Refresh delivery distances and carbon"
MODEL_NAME = "Delivery carbon"
REPORT_NAME = "Houston delivery carbon"


def export_definition(item: dict[str, Any], directory: Path) -> None:
    for part in item["parts"]:
        path = directory / part["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(part["payload"]))


def export_notebook(notebook: dict[str, Any]) -> None:
    path = Path("fabric/notebooks/Refresh_delivery_carbon.ipynb")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(notebook, indent=2) + "\n")


async def workspace_id(client: FabricClient, settings: FabricSettings) -> str:
    if settings.workspace_id:
        item = (await client.request("GET", f"workspaces/{settings.workspace_id}")).json()
        if item["displayName"] != settings.workspace_name:
            raise ValueError("Configured workspace ID and name disagree; refusing to update.")
        return settings.workspace_id
    workspaces = (await client.request("GET", "workspaces")).json()["value"]
    matches = [item for item in workspaces if item["displayName"] == settings.workspace_name]
    if len(matches) > 1:
        raise ValueError("Ambiguous workspace name; set workspace_id.")
    if matches:
        return matches[0]["id"]
    item = await client.complete(
        await client.request(
            "POST",
            "workspaces",
            {
                "displayName": settings.workspace_name,
                "capacityId": settings.capacity_id,
                "description": "Azure Maps delivery distance and illustrative carbon analytics",
            },
        )
    )
    return item["id"]


async def summary(client: FabricClient, workspace: str, lakehouse: str) -> dict[str, Any]:
    token = await client.credential.get_token("https://storage.azure.com/.default")
    response = await client.http.get(
        f"https://onelake.dfs.fabric.microsoft.com/{workspace}/{lakehouse}/Files/sample/refresh_summary.json",
        headers={"Authorization": f"Bearer {token.token}"},
    )
    response.raise_for_status()
    return response.json()


async def refresh_model(client: FabricClient, workspace: str, model: str) -> None:
    path = f"groups/{workspace}/datasets/{model}/refreshes"
    response = await client.request("POST", path, {}, powerbi=True)
    request_id = response.headers.get("x-ms-request-id")
    for _ in range(120):
        await asyncio.sleep(10)
        result = (await client.request("GET", path + "?$top=5", powerbi=True)).json()
        runs = result.get("value", [])
        if request_id:
            runs = [run for run in runs if run.get("requestId") == request_id]
        if not runs:
            continue
        run = runs[0]
        if run["status"] == "Completed":
            return
        if run["status"] in {"Failed", "Cancelled", "Disabled"}:
            raise RuntimeError(f"Semantic model refresh failed: {json.dumps(run)}")
    raise TimeoutError("Semantic model refresh is still running.")


async def verify_model(client: FabricClient, workspace: str, model: str) -> dict[str, Any]:
    query = (
        'EVALUATE ROW("Deliveries", [Deliveries], "Failed routes", [Failed routes], '
        '"Road km", [Road distance km], "CO2 kg", [Estimated CO2 kg], '
        '"Carbon cost USD", [Illustrative carbon cost USD], '
        '"Route points", COUNTROWS(route_points))'
    )
    response = await client.request(
        "POST",
        f"groups/{workspace}/datasets/{model}/executeQueries",
        {"queries": [{"query": query}], "serializerSettings": {"includeNulls": True}},
        powerbi=True,
    )
    result = response.json()
    if "error" in result or any("error" in item for item in result.get("results", [])):
        raise RuntimeError(f"Semantic model query failed: {json.dumps(result)}")
    return result


async def refresh_notebook(
    client: FabricClient, settings: FabricSettings, workspace: str, lakehouse: str
) -> str:
    notebook = build_notebook(
        workspace,
        lakehouse,
        settings.maps_client_id,
        settings.carbon_price_usd_per_tonne,
        settings.key_vault_url,
        settings.maps_secret_name,
    )
    await asyncio.to_thread(export_notebook, notebook)
    item = await client.publish(
        workspace,
        NOTEBOOK_NAME,
        "Notebook",
        definition({"notebook-content.ipynb": json.dumps(notebook)}, "ipynb"),
    )
    print(f"Running notebook {item['id']}", flush=True)
    print(json.dumps(await client.run_notebook(workspace, item["id"])), flush=True)
    return item["id"]


async def deploy(settings: FabricSettings, command: str) -> None:
    async with AzureCliCredential() as credential, httpx.AsyncClient(timeout=120) as http:
        client = FabricClient(http, credential)
        workspace = await workspace_id(client, settings)
        if command == "status":
            items = await client.items(workspace)
            print(json.dumps({"workspace": workspace, "items": items}, indent=2))
            lakehouses = [
                item
                for item in items
                if item["displayName"] == settings.lakehouse_name and item["type"] == "Lakehouse"
            ]
            if lakehouses:
                print(json.dumps(await summary(client, workspace, lakehouses[0]["id"]), indent=2))
            return
        lakehouse = await client.publish(workspace, settings.lakehouse_name, "Lakehouse")
        lakehouse_id = lakehouse["id"]
        if command == "deploy":
            await client.upload(
                workspace,
                lakehouse_id,
                "workbook_deliveries.csv",
                csv_bytes(read_workbook(settings.workbook)),
            )
            await client.upload(
                workspace,
                lakehouse_id,
                "workbook_route_results.csv",
                csv_bytes(read_workbook(settings.workbook, "Route Results")),
            )
            await client.upload(
                workspace,
                lakehouse_id,
                "csv_baseline.csv",
                csv_bytes(read_csv(settings.baseline_csv)),
            )
        if command != "publish-report":
            await refresh_notebook(client, settings, workspace, lakehouse_id)
        data_summary = await summary(client, workspace, lakehouse_id)
        print(json.dumps(data_summary), flush=True)
        if data_summary["successful"] != data_summary["deliveries"]:
            raise RuntimeError(
                "Some routes failed; inspect deliveries before publishing the report."
            )
        properties = (
            await client.request("GET", f"workspaces/{workspace}/lakehouses/{lakehouse_id}")
        ).json()["properties"]
        endpoint = properties["sqlEndpointProperties"]
        sync = await client.complete(
            await client.request(
                "POST",
                f"workspaces/{workspace}/sqlEndpoints/{endpoint['id']}/refreshMetadata",
                {"tables": [{"schema": "dbo", "tableNames": ["deliveries", "route_points"]}]},
            )
        )
        if any(table.get("status") == "Failure" for table in sync.get("value", [])):
            raise RuntimeError(f"SQL endpoint synchronization failed: {json.dumps(sync)}")
        model_payload = model_definition(endpoint["connectionString"], settings.lakehouse_name)
        await asyncio.to_thread(export_definition, model_payload, Path("fabric/semantic-model"))
        model = await client.publish(
            workspace,
            MODEL_NAME,
            "SemanticModel",
            model_payload,
        )
        print(f"Refreshing model {model['id']}", flush=True)
        await refresh_model(client, workspace, model["id"])
        query_result = await verify_model(client, workspace, model["id"])
        totals = query_result["results"][0]["tables"][0]["rows"][0]
        if totals["[Deliveries]"] != data_summary["deliveries"]:
            raise RuntimeError("Semantic model delivery count does not match the notebook output.")
        expected_totals = {
            "[Failed routes]": data_summary["deliveries"] - data_summary["successful"],
            "[Route points]": data_summary["route_points"],
            "[Road km]": data_summary["road_km"],
            "[CO2 kg]": data_summary["co2_kg"],
            "[Carbon cost USD]": data_summary["carbon_cost_usd"],
        }
        if any(
            not math.isclose(totals[name], expected, rel_tol=1e-9, abs_tol=1e-9)
            for name, expected in expected_totals.items()
        ):
            raise RuntimeError("Semantic model totals do not match the notebook output.")
        print(json.dumps(query_result), flush=True)
        report_payload = report_definition(model["id"])
        await asyncio.to_thread(export_definition, report_payload, Path("fabric/report"))
        report = await client.publish(workspace, REPORT_NAME, "Report", report_payload)
        binding = (
            await client.request("GET", f"groups/{workspace}/reports/{report['id']}", powerbi=True)
        ).json()
        if binding.get("datasetId") != model["id"]:
            raise RuntimeError("Published report is not bound to the expected semantic model.")
        receipt = {
            "workspace_id": workspace,
            "lakehouse_id": lakehouse_id,
            "model_id": model["id"],
            "report_id": report["id"],
            "report_url": binding["webUrl"],
            "summary": data_summary,
        }
        serialized = json.dumps(receipt, indent=2) + "\n"
        await asyncio.to_thread(Path("fabric/deployment.json").write_text, serialized)
        print(serialized, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deploy and refresh Fabric delivery carbon analytics."
    )
    parser.add_argument("command", choices=["deploy", "refresh", "publish-report", "status"])
    parser.add_argument("--config", type=Path, default=Path("fabric/config.json"))
    args = parser.parse_args()
    settings = FabricSettings(**json.loads(args.config.read_text()))
    asyncio.run(deploy(settings, args.command))


if __name__ == "__main__":
    main()
