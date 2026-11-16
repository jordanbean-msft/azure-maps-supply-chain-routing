# Contributor guide

This branch contains Excel delivery samples and Fabric notebook/setup tooling,
not the archived web application. Follow `.github/copilot-instructions.md` and
the applicable files in `.github/instructions/`.

Use `uv` for Python operations. Validate with `uv run ruff check .`,
`uv run ruff format --check .`, `uv run mypy src/`, `uv run pytest -W error`,
and `uv build`. Tests mock external services and must not require Azure access.

Keep sample assets, Fabric definitions, supporting documentation, and developer
tasks consistent. Never commit credentials or overwrite the archived application
branch. Do not deploy or refresh cloud resources as part of local validation.
