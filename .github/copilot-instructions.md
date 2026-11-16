---
description: Guidance for the Excel samples and Fabric delivery carbon tooling
---

## Scope and layout

`main` contains only Excel and companion Python/Synapse samples, Fabric notebooks
and setup/report tooling, associated tests, documentation, and developer tooling.
The original web application is preserved on `archive/web-app-before-fabric-only`;
do not reintroduce its API, frontend, containers, or Terraform on this branch.

- `sample/`: original Excel, CSV, Python, and Synapse assets.
- `fabric/`: configuration, Fabric notebook, model/report definitions, receipt.
- `src/template_repository/fabric/`: Fabric setup and Azure Maps helpers.
- `tests/`: deterministic offline Fabric/notebook tests.
- `docs/`: Excel, notebook, and Fabric operations guides.

## Engineering standards

- Always use uv for environment and dependency management.
- Prefer Microsoft-maintained SDKs when they satisfy the requirement.
- Keep imports at the top, grouped and sorted; no lazy or guarded imports.
- Use pydantic-settings for centralized configuration.
- Keep public functions explicitly typed and modules single-purpose.
- Use dependency injection and async interfaces for external network services.
- Use structured logging; never print credentials or commit keys.
- Preserve the original `sample/` implementations unless explicitly requested.
- Mock cloud services in tests; no billable requests during validation.
- Keep `.vscode/tasks.json` and `.vscode/launch.json` aligned with entry points.

## Validation

```bash
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
uv run pytest -W error
uv build
```

Ruff excludes the unchanged original `sample/` script and notebook.
Fabric configuration is nonsecret. Review commands and obtain approval before
updating cloud resources or running billable enrichment.
