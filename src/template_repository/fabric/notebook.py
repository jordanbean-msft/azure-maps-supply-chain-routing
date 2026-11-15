import json
from pathlib import Path
from typing import Any


def code_cell(source: str, *, parameters: bool = False) -> dict[str, Any]:
    return {
        "cell_type": "code",
        "metadata": {"tags": ["parameters"]} if parameters else {},
        "source": source.splitlines(keepends=True),
        "execution_count": None,
        "outputs": [],
    }


def build_notebook(
    workspace: str,
    lakehouse: str,
    maps_client: str,
    carbon_price: float,
    key_vault_url: str,
    secret_name: str,
) -> dict[str, Any]:
    spark_imports = """import httpx
import notebookutils
from pyspark.sql import SparkSession
from pyspark.sql.types import DoubleType, LongType, StringType, StructField, StructType
"""
    enrichment = (
        Path(__file__)
        .with_name("maps.py")
        .read_text()
        .replace("import asyncio\n", "import asyncio\nimport csv\nimport io\n")
        .replace("import httpx\n", spark_imports)
    )
    parameters = (
        f"MAPS_CLIENT_ID = {maps_client!r}\n"
        f"CARBON_PRICE_USD_PER_TONNE = {carbon_price!r}\n"
        f"KEY_VAULT_URL = {key_vault_url!r}\n"
        f"MAPS_SECRET_NAME = {secret_name!r}\n"
        "INPUT_FILE = 'Files/sample/workbook_deliveries.csv'\n"
        "MAX_ROWS = 1000\n"
    )
    run = """
spark = SparkSession.builder.getOrCreate()

input_directory, input_name = INPUT_FILE.rsplit("/", 1)
file_info = next(
    entry for entry in notebookutils.fs.ls(input_directory) if entry.name == input_name
)
if file_info.size > 4 * 1024 * 1024:
    raise ValueError("Input exceeds the 4 MiB driver-side file limit; split the batch.")

maps_key = notebookutils.credentials.getSecret(KEY_VAULT_URL, MAPS_SECRET_NAME)

async def maps_key_provider() -> str:
    return maps_key

input_text = notebookutils.fs.head(INPUT_FILE, 4 * 1024 * 1024)
deliveries = list(csv.DictReader(io.StringIO(input_text)))
async with httpx.AsyncClient(timeout=60) as http:
    maps = DeliveryMaps(
        http, None, MAPS_CLIENT_ID, subscription_key_provider=maps_key_provider
    )
    enriched = await maps.enrich(deliveries, CARBON_PRICE_USD_PER_TONNE, MAX_ROWS)

numeric_columns = {
    "Plant_Latitude", "Plant_Longitude", "ManfactSupplier_Latitude",
    "ManfactSupplier_Longitude", "Part_Qty", "Part_NetWeight_kg", "Distance_in_km",
    "Emissions_factor_kgCO2_per_km", "Trip_multiplier", "Driving_distance_km",
    "CO2_emitted_kg", "Carbon_cost_USD", "Carbon_price_USD_per_tonne",
    "Supplier_route_latitude", "Supplier_route_longitude",
    "Plant_route_latitude", "Plant_route_longitude",
}
columns = sorted({key for row in enriched for key in row})
schema = StructType([
    StructField(name, DoubleType() if name in numeric_columns else StringType(), True)
    for name in columns
])
typed = []
for row in enriched:
    converted: dict[str, Any] = {}
    for name in columns:
        value = row.get(name)
        if value in ("", None):
            converted[name] = None
        elif name in numeric_columns:
            try:
                numeric = float(value)
                converted[name] = numeric if math.isfinite(numeric) else None
            except (ValueError, TypeError):
                converted[name] = None
        else:
            converted[name] = str(value)
    typed.append(converted)

points = route_points(enriched)
point_schema = StructType([
    StructField("Delivery_ID", StringType(), False),
    StructField("Path_ID", StringType(), False),
    StructField("Route_segment", LongType(), False),
    StructField("Point_sequence", LongType(), False),
    StructField("Longitude", DoubleType(), False),
    StructField("Latitude", DoubleType(), False),
])
df = spark.createDataFrame(typed, schema)
route_df = spark.createDataFrame(points, point_schema)
df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("deliveries")
route_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("route_points")

features = [
    {
        "type": "Feature",
        "geometry": json.loads(row["Route_geojson"]),
        "properties": {
            "Delivery_ID": row["Delivery_ID"],
            "CO2_emitted_kg": row["CO2_emitted_kg"],
            "Carbon_cost_USD": row["Carbon_cost_USD"],
        },
    }
    for row in enriched if row["Route_Status"] == "OK"
]
notebookutils.fs.put(
    "Files/sample/routes.geojson",
    json.dumps({"type": "FeatureCollection", "features": features}, allow_nan=False),
    True,
)
summary = {
    "deliveries": len(enriched),
    "successful": sum(row["Route_Status"] == "OK" for row in enriched),
    "route_points": len(points),
    "road_km": sum(row["Driving_distance_km"] or 0 for row in enriched),
    "co2_kg": sum(row["CO2_emitted_kg"] or 0 for row in enriched),
    "carbon_cost_usd": sum(row["Carbon_cost_USD"] or 0 for row in enriched),
    "carbon_price_usd_per_tonne": CARBON_PRICE_USD_PER_TONNE,
}
notebookutils.fs.put("Files/sample/refresh_summary.json", json.dumps(summary), True)
print(json.dumps(summary))
if not summary["successful"]:
    raise RuntimeError("No routes succeeded. Error rows persisted; check Maps identity and permissions.")
"""
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Synapse PySpark",
                "language": "python",
                "name": "synapse_pyspark",
            },
            "language_info": {"name": "python"},
            "dependencies": {
                "lakehouse": {
                    "default_lakehouse": lakehouse,
                    "default_lakehouse_name": "delivery_carbon",
                    "default_lakehouse_workspace_id": workspace,
                    "known_lakehouses": [{"id": lakehouse}],
                }
            },
        },
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# Houston delivery distance and carbon\n",
                    "Workbook Deliveries -> Azure Maps geocoding/road routing -> Delta -> Power BI.\n",
                    "One row is one vehicle trip. CO2 is an illustrative estimate, not an Azure Maps output.\n",
                    "CO2 kg = road km x kg CO2/vehicle-km x trip multiplier. Cost USD = CO2 kg / 1000 x USD/tonne.\n",
                    "Driving mode is not restricted commercial-truck routing. No straight-line fallback.\n",
                    "Azure Maps calls run sequentially on the driver, never Spark executors.\n",
                    "The Maps key is read from Key Vault at runtime; it is never stored in notebook source or data.\n",
                ],
            },
            code_cell(enrichment),
            code_cell(parameters, parameters=True),
            code_cell(run),
        ],
    }
    template_path = Path("fabric/notebooks/Refresh_delivery_carbon.ipynb")
    if template_path.is_file():
        template = json.loads(template_path.read_text(encoding="utf-8"))
        parameter_cells = [
            cell
            for cell in template["cells"]
            if "parameters" in cell.get("metadata", {}).get("tags", [])
        ]
        if len(parameter_cells) != 1 or parameter_cells[0]["cell_type"] != "code":
            raise ValueError("Notebook template must contain exactly one parameters code cell.")
        parameter_cells[0]["source"] = parameters.splitlines(keepends=True)
        for cell in template["cells"]:
            if cell["cell_type"] == "code":
                cell["execution_count"] = None
                cell["outputs"] = []
        notebook["cells"] = template["cells"]
    return notebook
