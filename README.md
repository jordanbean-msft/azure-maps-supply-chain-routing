---
title: Delivery distance and carbon analytics
description: Excel delivery samples, Azure Maps enrichment, and Microsoft Fabric notebook and Power BI setup.
---

# Delivery distance and carbon analytics

Use Azure Maps road distances to estimate vehicle-trip CO2 in Excel or Microsoft
Fabric. This repository contains the Houston workbook and companion CSV,
Python/Synapse samples, a staged Fabric notebook, and the setup code for a
Lakehouse, Direct Lake semantic model, and Power BI report.

The original React/FastAPI web application, its infrastructure, and its
documentation are preserved on
[`archive/web-app-before-fabric-only`](https://github.com/jordanbean-msft/azure-maps-supply-chain-routing/tree/archive/web-app-before-fabric-only).
They are not part of `main`. Removing their source does not delete deployed
Azure resources or stop their charges.

## Excel sample

Open [`sample/Houston_Delivery_CO2.xlsx`](sample/Houston_Delivery_CO2.xlsx) in
desktop Excel for Windows. Follow the
[Excel sample guide](docs/excel-sample-approach.md) for Power Query setup,
Azure Maps authentication, worksheet formulas, and the standalone Python and
Synapse alternatives. The supplied CSV is a reference snapshot, not live data.

Use synthetic data only. Never commit Maps keys or credential-bearing workbook
copies. Route distances are measured road distances; CO2 factors and carbon
prices are configurable assumptions, not Azure Maps emissions measurements.
These samples do not optimize shipments or provide commercial-truck routing.

## Fabric notebook and report

Read the [Fabric notebook guide](docs/fabric-notebook-approach.md) for input
contracts and the seven runnable stages. See
[Fabric setup and operations](docs/fabric-delivery-carbon.md) for permissions,
configuration, the report link, refresh behavior, and recorded deployment details.

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Azure CLI, a Fabric
workspace on active capacity, and the documented Maps/Key Vault and workspace
permissions. Review `fabric/config.json` before running commands that update
cloud resources and incur charges.

```bash
uv sync --extra dev
az login
uv run python -m template_repository.fabric.cli deploy
uv run python -m template_repository.fabric.cli status
```

`deploy` uploads sanitized sample inputs and runs enrichment. For existing inputs,
use `refresh`; use `publish-report` to update the model/report without repeating
Maps requests:

```bash
uv run python -m template_repository.fabric.cli refresh
uv run python -m template_repository.fabric.cli publish-report
```

## Repository layout

| Path | Contents |
| --- | --- |
| `sample/` | Excel workbook, reference CSV, standalone Python script, Synapse notebook |
| `fabric/` | Nonsecret setup configuration, Fabric notebook, semantic model/report definitions, deployment receipt |
| `src/template_repository/fabric/` | Fabric setup, publication, sample normalization, and Maps enrichment helpers |
| `tests/` | Offline Fabric and notebook tests with mocked cloud services |
| `docs/` | Excel, notebook, and Fabric operations guides |
| `.vscode/` | Setup, build, validation, Fabric operations, and debugger configurations |

The Python namespace remains `template_repository` so existing Fabric commands
and documentation continue to work. There is no web server entry point.
Azure integrations use Microsoft-maintained SDKs. HTTPX provides the existing
async REST transport; Microsoft does not publish an equivalent general-purpose
Python async HTTP client.

## Development and validation

```bash
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
uv run pytest -W error
uv build
```

The original standalone script and Synapse notebook in `sample/` are retained
unchanged and excluded from Ruff checks; the Fabric implementation, tests, and
Fabric notebook are checked. Tests require no Azure credentials or live services.
Use `uv run ruff format .` to format maintained code.
Coverage remains available through `uv run pytest --cov`; the former web app's
aggregate 70% coverage gate no longer applies to this reduced repository.

## License and disclaimer

See [LICENSE](LICENSE). This demonstration is provided as-is, without warranty;
route, emissions, and illustrative carbon-cost estimates are not logistics
guarantees or certified emissions results.
