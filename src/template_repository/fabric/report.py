import json
from typing import Any

from template_repository.fabric.client import definition

SCHEMA_BASE = "https://developer.microsoft.com/json-schemas/fabric/item/report"


def projection(table: str, name: str, *, measure: bool = False) -> dict[str, Any]:
    kind = "Measure" if measure else "Column"
    return {
        "field": {kind: {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}},
        "queryRef": f"{table}.{name}",
        "nativeQueryRef": name,
    }


def visual(
    name: str,
    visual_type: str,
    title: str,
    roles: dict[str, list[dict[str, Any]]],
    x: int,
    y: int,
    width: int,
    height: int,
) -> dict[str, Any]:
    return {
        "$schema": f"{SCHEMA_BASE}/definition/visualContainer/2.4.0/schema.json",
        "name": name,
        "position": {"x": x, "y": y, "z": 0, "height": height, "width": width},
        "visual": {
            "visualType": visual_type,
            "query": {
                "queryState": {role: {"projections": fields} for role, fields in roles.items()}
            },
            "visualContainerObjects": {
                "title": [
                    {
                        "properties": {
                            "show": {"expr": {"Literal": {"Value": "true"}}},
                            "text": {
                                "expr": {"Literal": {"Value": "'" + title.replace("'", "''") + "'"}}
                            },
                        }
                    }
                ]
            },
            "drillFilterOtherVisuals": True,
        },
    }


def report_definition(model_id: str) -> dict[str, Any]:
    parts = {
        "definition/version.json": {
            "$schema": f"{SCHEMA_BASE}/definition/versionMetadata/1.0.0/schema.json",
            "version": "2.0.0",
        },
        "definition.pbir": {
            "$schema": f"{SCHEMA_BASE}/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {
                "byConnection": {"connectionString": f"semanticmodelid={model_id}"}
            },
        },
        "definition/report.json": {
            "$schema": f"{SCHEMA_BASE}/definition/report/3.0.0/schema.json",
            "themeCollection": {},
        },
        "definition/pages/pages.json": {
            "$schema": f"{SCHEMA_BASE}/definition/pagesMetadata/1.0.0/schema.json",
            "pageOrder": ["overview", "quality"],
            "activePageName": "overview",
        },
    }
    for name, title in (
        ("overview", "Houston | Azure Maps & estimated carbon"),
        ("quality", "Delivery detail & data quality"),
    ):
        parts[f"definition/pages/{name}/page.json"] = {
            "$schema": f"{SCHEMA_BASE}/definition/page/2.0.0/schema.json",
            "name": name,
            "displayName": title,
            "displayOption": "FitToPage",
            "height": 900,
            "width": 1440,
        }

    def add(page: str, item: dict[str, Any]) -> None:
        parts[f"definition/pages/{page}/visuals/{item['name']}/visual.json"] = item

    for index, measure in enumerate(
        (
            "Deliveries",
            "Road distance km",
            "Estimated CO2 kg",
            "Illustrative carbon cost USD",
            "Failed routes",
        )
    ):
        add(
            "overview",
            visual(
                f"kpi{index}",
                "card",
                measure,
                {"Values": [projection("deliveries", measure, measure=True)]},
                16 + index * 284,
                12,
                272,
                100,
            ),
        )
    for index, (field, title) in enumerate(
        (
            ("PlantName", "Plant"),
            ("ManfactSupplier_Name", "Supplier"),
            ("Route_Status", "Route status"),
        )
    ):
        add(
            "overview",
            visual(
                f"filter{index}",
                "slicer",
                title,
                {"Values": [projection("deliveries", field)]},
                16 + index * 474,
                126,
                458,
                100,
            ),
        )
    route_map = visual(
        "routemap",
        "azureMap",
        "Azure Maps road paths | select a route to filter",
        {
            "Y": [projection("route_points", "Latitude")],
            "X": [projection("route_points", "Longitude")],
            "PathID": [projection("route_points", "Path_ID")],
            "PointOrder": [projection("route_points", "Point_sequence")],
            "Series": [projection("deliveries", "PlantName")],
            "Tooltips": [
                projection("route_points", "Delivery_ID"),
                projection("deliveries", "Estimated CO2 kg", measure=True),
                projection("deliveries", "Illustrative carbon cost USD", measure=True),
            ],
        },
        16,
        242,
        920,
        510,
    )
    route_map["visual"]["objects"] = {
        "pathLayer": [
            {
                "properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "strokeWidth": {"expr": {"Literal": {"Value": "3D"}}},
                }
            }
        ],
        "bubbleLayer": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}],
    }
    add("overview", route_map)
    add(
        "overview",
        visual(
            "suppliercarbon",
            "barChart",
            "Estimated CO2 kg by supplier",
            {
                "Category": [projection("deliveries", "ManfactSupplier_Name")],
                "Y": [projection("deliveries", "Estimated CO2 kg", measure=True)],
                "Tooltips": [
                    projection("deliveries", "Illustrative carbon cost USD", measure=True)
                ],
            },
            952,
            242,
            472,
            510,
        ),
    )
    add(
        "overview",
        visual(
            "assumptions",
            "tableEx",
            "Illustrative vehicle-km model | cost = CO2 kg / 1,000 x USD/tonne | not certified",
            {
                "Values": [
                    projection("deliveries", "Emissions_factor_kgCO2_per_km"),
                    projection("deliveries", "Carbon price USD per tonne", measure=True),
                    projection("deliveries", "Last refresh UTC", measure=True),
                ]
            },
            16,
            768,
            1408,
            116,
        ),
    )
    add(
        "quality",
        visual(
            "deliverydetail",
            "tableEx",
            "Delivery-level measures (not multiplied by route-point counts); errors retain null metrics",
            {
                "Values": [
                    projection("deliveries", name, measure=is_measure)
                    for name, is_measure in (
                        ("Delivery_ID", False),
                        ("PlantName", False),
                        ("ManfactSupplier_Name", False),
                        ("Road distance km", True),
                        ("Estimated CO2 kg", True),
                        ("Illustrative carbon cost USD", True),
                        ("Route_Status", False),
                        ("Route_Error_Reason", False),
                        ("Supplier_matched_address", False),
                        ("Plant_matched_address", False),
                        ("Refreshed_UTC", False),
                    )
                ]
            },
            16,
            16,
            1408,
            868,
        ),
    )
    return definition({path: json.dumps(content) for path, content in parts.items()}, "PBIR")
