---
title: Fabric delivery distance and carbon analytics
description: Deployment details, refresh commands, authentication, and recorded validation for the Fabric delivery carbon report.
---

## Approach guides

Use the [detailed Fabric notebook guide](fabric-notebook-approach.md) for input
contracts, the seven processing stages, API behavior, storage, and publication.
Use the [Excel sample guide](excel-sample-approach.md) for workbook setup,
Power Query, worksheet formulas, and the companion Python/Synapse alternatives.

## Report access

[Open the Power BI report](https://app.powerbi.com/groups/cb3d235a-f6a5-4d88-b29f-aacac1bb8907/reports/f13c2cce-b1d5-46ea-a912-2c2b60f5b37e).

## Deployed resources

| Item | Name / ID |
| --- | --- |
| Workspace | `supply-chain-routing` / `cb3d235a-f6a5-4d88-b29f-aacac1bb8907` |
| Existing F2 capacity | `fabricrjbeus2` / `67635827-844f-41d4-b69f-3a807e03d125` |
| Lakehouse | `delivery_carbon` / `6e323a75-0a0c-43ce-9092-2a75622784d5` |
| Refresh notebook | `Refresh delivery distances and carbon` / `156468ff-54b1-4181-b39e-1202cad247a5` |
| Direct Lake semantic model | `Delivery carbon` / `caa155e4-c9a7-4a47-911e-e6509dc1e1d1` |
| Power BI report | `Houston delivery carbon` / `f13c2cce-b1d5-46ea-a912-2c2b60f5b37e` |
| Maps account used by notebook | `maps-scroute-eus2-local` in `rg-scroute-eus2` |
| Dedicated Key Vault | `kv-scroute-fabric-rjb` in `rg-scroute-eus2` |

The approved capacity is **left active and billable** for report use. Pausing it
interrupts this report and other workspaces assigned to the same capacity. No
recurring refresh schedule is enabled.

The output is an interactive, two-page **dashboard-style Power BI report**, not a
separate Power BI Service Dashboard with pinned tiles. The overview includes road
geometry on Azure Maps, delivery/distance/CO2/cost/error cards, supplier CO2,
plant/supplier/status filters, refresh time, and explicit pricing assumptions.
The detail page includes matched addresses, delivery metrics, and error reasons.

## Data flow and calculation

`sample/Houston_Delivery_CO2.xlsx`, sheet `Deliveries`, is the refresh input.
`Route Results` and the supplied live CSV are retained as reference snapshots.
The CLI normalizes these sheets to UTF-8 CSV without executing formulas or Power
Query. It removes key-named columns **before** uploading; the original workbook,
which could contain embedded credentials, is not uploaded.

OneLake files:

- `Files/sample/workbook_deliveries.csv`: normalized workbook input.
- `Files/sample/workbook_route_results.csv`: workbook reference results.
- `Files/sample/csv_baseline.csv`: supplied live CSV reference results.
- `Files/sample/routes.geojson`: road paths from the latest successful routes.
- `Files/sample/refresh_summary.json`: latest notebook totals.

The notebook independently geocodes the supplier and plant address columns using
Azure Maps Geocoding `2025-01-01`, then requests supplier-to-plant road paths using
Route Directions `2025-01-01`. It uses `driving` and `fastestWithoutTraffic`, matching
the sample's light-vehicle trip model; this is **not restricted commercial-truck
routing**. Address and directional route caches last for one run only.

```text
Estimated CO2 kg = road km x emissions factor kg CO2/vehicle-km x trip multiplier
Illustrative carbon cost USD = estimated CO2 kg / 1,000 x carbon price USD/tonne
```

The default factor in the sample is **0.270 kg CO2/vehicle-km**, and the approved
illustrative carbon price is **USD 100/tonne**. Azure Maps supplies road distances,
coordinates, and paths; it does **not** supply this emissions factor, a certified
emissions result, or the carbon price. One row represents one vehicle trip.
Part quantities/weights are not multiplied into this vehicle-km calculation.
The trip multiplier approximates equivalent legs; it does not request a reverse
route. Reference/Haversine coordinates are never used as a road-distance fallback.

`deliveries` is a typed Delta table with one row per delivery. `route_points`
contains the API's actual ordered road geometry, keyed by delivery and segment.
The semantic model aggregates costs from `deliveries`, not from the point table,
preventing thousands of geometry points from inflating costs. `Path_ID` and
`Point_sequence` identify separate paths and preserve their point order.

Failures clear prior distance, coordinates, geometry, CO2, and cost, retaining null
metrics and explicit error columns. Duplicate delivery IDs and invalid factors,
addresses, multipliers, or coordinates are rejected. The batch limit is 1,000
rows. Calls execute sequentially on the notebook driver, not Spark workers.
Transient failures/throttling retry within a fixed budget. These are small-batch
demo safeguards, not a bulk-routing platform or account-quota guarantee.

## Authentication

The deployment CLI uses Microsoft's `AzureCliCredential` and the signed-in Azure
CLI user. Fabric REST, OneLake, and Power BI each receive their own scoped token.
`fab auth login` could not run interactively in this terminal, so deployment uses
Fabric REST via Azure CLI authentication instead of storing Fabric credentials.

Fabric NotebookUtils did not support obtaining an Azure Maps audience token in
the tested runtime. With explicit approval, the notebook instead reads
`azure-maps-key` from `https://kv-scroute-fabric-rjb.vault.azure.net/` at runtime.
The secret was transferred directly from the existing key-enabled local Maps
account to Key Vault in process memory, without printing or saving its value.
The production Maps account remains key-disabled. The new vault uses Azure RBAC
and purge protection, and was provisioned via Azure CLI. The web application's
Terraform deployment is archived on `archive/web-app-before-fabric-only`.

The executing user needs secret-read permission on that vault. The initial
provisioning user was granted vault-scoped `Key Vault Secrets Officer` to set and
maintain this one secret; other notebook users should receive only `Key Vault
Secrets User`. Future scheduled runs must use an identity with appropriate vault
and workspace access. Keep the vault secret synchronized when rotating the Maps
account key. Never paste a key into the notebook, config, CSV, CLI arguments, or
report. The Python Maps component also supports Entra authentication for hosts
that can obtain a Maps token; the CLI user was granted account-scoped Maps Data
Reader during that validation.

## Deploy and refresh

Run from the repository root, with an active capacity and the necessary Fabric
workspace, OneLake, Power BI, and Key Vault permissions:

```bash
az login
uv sync --extra dev
uv run python -m template_repository.fabric.cli deploy
uv run python -m template_repository.fabric.cli status
```

`fabric/config.json` contains only nonsecret deployment settings. For another
workspace, change the name/capacity and clear `workspace_id` to resolve/create it;
configure the new vault, Maps account, and source paths first. The CLI does not
silently resume a capacity, grant roles, create a vault, or change account
authentication settings.

`deploy` uploads normalized local inputs and runs enrichment. `refresh` reruns
the notebook against existing OneLake input, then refreshes the model and report.
`publish-report` updates only the semantic model/report from existing Delta
tables without repeating billable Maps requests:

```bash
uv run python -m template_repository.fabric.cli refresh
uv run python -m template_repository.fabric.cli publish-report
```

Change `carbon_price_usd_per_tonne` in the config, then run `refresh` to recalculate
costs. To change source deliveries, edit the local workbook and run `deploy`, or
replace `Files/sample/workbook_deliveries.csv` and run `refresh`. Refresh overwrites
the two current-state Delta tables; it is not a historical snapshot store.

The CLI publishes `fabric/notebooks/Refresh_delivery_carbon.ipynb`, exports the
model/report definitions, and saves `fabric/deployment.json`. When the local
notebook exists, the notebook factory preserves its cells and documentation,
replaces the tagged parameters cell, clears execution outputs, and applies the
target workspace and Lakehouse metadata. If the file is absent, the factory
generates the original single-call workflow from the local Maps module.

The checked-in notebook exposes seven separate runnable stages:

1. Read and validate deliveries into `validated`, without network requests.
2. Geocode addresses into `geocoded`, with matched addresses and road-access points.
3. Request road routes into `routed`, with distance and geometry.
4. Calculate carbon estimates into `enriched`, without network requests.
5. Prepare typed delivery data and an explicit Spark schema.
6. Overwrite the delivery and ordered route-point Delta tables.
7. Export GeoJSON routes and the JSON refresh summary.

Run these cells in order. Each stage preserves the earlier snapshots and prints
full result rows and available status counts as indented JSON, including geometry
and route points in later stages. Key-named input columns are excluded; business
data still appears in notebook output. Intermediate successful states are `VALIDATED`, `GEOCODED`, and
`ROUTED`; only completed carbon calculations receive `OK`. Errors remain `ERROR`
and are skipped by later stages. Address and directional-route caches are scoped
to each network stage run, so rerunning a stage can repeat billable requests.
After editing upstream inputs, rerun all downstream stages before saving results.

The CLI explicitly synchronizes the SQL endpoint's metadata before refreshing
Direct Lake: a newly written Delta table can exist in OneLake before SQL discovery
finishes. It checks notebook completion, model DAX totals against notebook totals,
and report-to-model binding before reporting success.

VS Code includes `fabric:deploy`, `fabric:refresh`, `fabric:status`, `fabric:test`,
and a Fabric deployment debugger configuration.

## Validation

```bash
uv run pytest tests/test_fabric.py tests/test_fabric_notebook.py -W error
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
```

The original unmodified script/notebook under `sample/` have existing lint
violations and are excluded from Ruff checks.

Live validation on November 9, 2026 produced 24 successful deliveries, 5,868 road
points, 213.35 road km, 57.6045 kg estimated CO2, and USD 5.76045 illustrative cost.
Report definitions were validated against Microsoft's PBIR JSON schemas, and the
report was rendered in headless Chromium using Microsoft's Power BI embed SDK
with Azure CLI authentication. The Azure Maps visual requires the tenant's Azure
Maps visual setting to remain enabled. F2 report sharing still requires the
applicable Power BI licenses and workspace permissions.
