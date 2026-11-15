import json
from typing import Any

from template_repository.fabric.client import definition

DELIVERY_NUMBERS = {
    "Driving_distance_km",
    "CO2_emitted_kg",
    "Carbon_cost_USD",
    "Carbon_price_USD_per_tonne",
    "Emissions_factor_kgCO2_per_km",
    "Trip_multiplier",
    "Supplier_route_latitude",
    "Supplier_route_longitude",
    "Plant_route_latitude",
    "Plant_route_longitude",
}
DELIVERY_TEXT = {
    "Delivery_ID",
    "PlantCode",
    "PlantName",
    "ManfactSupplier_ID",
    "ManfactSupplier_Name",
    "Supplier_matched_address",
    "Plant_matched_address",
    "Route_Status",
    "Route_Error_Reason",
    "Route_Error_Detail",
    "Refreshed_UTC",
}
MEASURES = {
    "Deliveries": ("COUNTROWS(deliveries)", "#,0"),
    "Successful routes": (
        'COALESCE(CALCULATE(COUNTROWS(deliveries), deliveries[Route_Status] = "OK"), 0)',
        "#,0",
    ),
    "Failed routes": (
        'COALESCE(CALCULATE(COUNTROWS(deliveries), deliveries[Route_Status] <> "OK"), 0)',
        "#,0",
    ),
    "Road distance km": ("SUM(deliveries[Driving_distance_km])", "#,0.00"),
    "Estimated CO2 kg": ("SUM(deliveries[CO2_emitted_kg])", "#,0.000"),
    "Illustrative carbon cost USD": ("SUM(deliveries[Carbon_cost_USD])", "$#,0.00"),
    "Carbon price USD per tonne": ("MAX(deliveries[Carbon_price_USD_per_tonne])", "$#,0.00"),
    "Last refresh UTC": ("MAX(deliveries[Refreshed_UTC])", ""),
}


def model_definition(sql_server: str, lakehouse_name: str = "delivery_carbon") -> dict[str, Any]:
    tables = []
    schemas = {
        "deliveries": {
            **dict.fromkeys(sorted(DELIVERY_TEXT), "string"),
            **dict.fromkeys(sorted(DELIVERY_NUMBERS), "double"),
        },
        "route_points": {
            "Delivery_ID": "string",
            "Path_ID": "string",
            "Route_segment": "int64",
            "Point_sequence": "int64",
            "Longitude": "double",
            "Latitude": "double",
        },
    }
    for name, fields in schemas.items():
        columns = []
        for field, data_type in fields.items():
            column: dict[str, Any] = {
                "name": field,
                "dataType": data_type,
                "sourceColumn": field,
                "summarizeBy": "none",
            }
            if "latitude" in field.lower():
                column["dataCategory"] = "Latitude"
            elif "longitude" in field.lower():
                column["dataCategory"] = "Longitude"
            if name == "deliveries" and field == "Delivery_ID":
                column["isKey"] = True
            columns.append(column)
        table: dict[str, Any] = {
            "name": name,
            "columns": columns,
            "partitions": [
                {
                    "name": name,
                    "mode": "directLake",
                    "source": {
                        "type": "entity",
                        "entityName": name,
                        "schemaName": "dbo",
                        "expressionSource": "DatabaseQuery",
                    },
                }
            ],
        }
        if name == "deliveries":
            table["measures"] = [
                {"name": measure, "expression": expression, "formatString": fmt}
                for measure, (expression, fmt) in MEASURES.items()
            ]
        tables.append(table)
    model = {
        "compatibilityLevel": 1604,
        "model": {
            "culture": "en-US",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "expressions": [
                {
                    "name": "DatabaseQuery",
                    "kind": "m",
                    "expression": (
                        f"let Source = Sql.Database({json.dumps(sql_server)}, "
                        f"{json.dumps(lakehouse_name)}) in Source"
                    ),
                }
            ],
            "tables": tables,
            "relationships": [
                {
                    "name": "delivery_route_points",
                    "fromTable": "route_points",
                    "fromColumn": "Delivery_ID",
                    "fromCardinality": "many",
                    "toTable": "deliveries",
                    "toColumn": "Delivery_ID",
                    "toCardinality": "one",
                    "crossFilteringBehavior": "bothDirections",
                }
            ],
        },
    }
    return definition(
        {
            "model.bim": json.dumps(model),
            "definition.pbism": json.dumps({"version": "1.0", "settings": {}}),
        },
        "TMSL",
    )
