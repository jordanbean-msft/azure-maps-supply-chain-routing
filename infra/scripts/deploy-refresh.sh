#!/usr/bin/env sh
set -eu

# azd invokes service hooks from each service's project directory.
python3 - "${1:?Expected api or web service}" <<'PY'
import json
import os
import subprocess
import sys

service = sys.argv[1]
if service not in {"api", "web"}:
    raise SystemExit("Expected api or web service")


def azure(*args: str) -> dict:
    result = subprocess.run(
        ["az", *args, "--output", "json", "--only-show-errors"],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def patch_template(resource: dict, template: dict) -> None:
    template.pop("revisionSuffix", None)
    azure(
        "rest", "--method", "patch",
        "--uri", f"{resource['id']}?api-version=2025-01-01",
        "--headers", "Content-Type=application/json",
        "--body", json.dumps({"properties": {"template": template}}),
    )


group = os.environ["AZURE_RESOURCE_GROUP"]
app_name = os.environ[f"AZURE_CONTAINER_APP_{service.upper()}_NAME"]
app = azure("containerapp", "show", "--resource-group", group, "--name", app_name)
template = app["properties"]["template"]
container = next(c for c in template["containers"] if c["name"] == service)
image = container["image"]
registry = os.environ["AZURE_CONTAINER_REGISTRY_ENDPOINT"]
if not image.startswith(f"{registry}/") or image.endswith(":latest"):
    raise SystemExit("Refusing to activate a bootstrap, foreign-registry or latest-tag image")
if "@sha256:" not in image and ":" not in image.rsplit("/", 1)[-1]:
    raise SystemExit("A digest or explicit deployment tag is required")

# Clear only the provisioning command. Preserve identity, probes, environment,
# resource bounds, registry configuration and the deployed immutable image tag.
if container.get("command"):
    container["command"] = []
    patch_template(app, template)

if service == "api":
    job = azure(
        "containerapp", "job", "show", "--resource-group", group,
        "--name", os.environ["AZURE_CONTAINER_APP_REFRESH_JOB_NAME"],
    )
    job_template = job["properties"]["template"]
    job_container = next(c for c in job_template["containers"] if c["name"] == "refresh")
    job_container["image"] = image
    job_container["command"] = ["python", "-m", "template_repository.refresh"]
    patch_template(job, job_template)
    print("Refresh job synchronized to the deployed API image; managed identity preserved.")
else:
    print("Web application entry point activated; managed identity preserved.")
PY
