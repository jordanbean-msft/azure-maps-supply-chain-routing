#!/usr/bin/env sh
set -eu

# azd invokes service hooks from each service's project directory.
python3 - "${1:?Expected api or web service}" <<'PY'
import json
import os
import subprocess
import sys

service = sys.argv[1]
api_version = "2025-01-01"
if service not in {"api", "web"}:
    raise SystemExit("Expected api or web service")


def azure(*args: str) -> dict:
    result = subprocess.run(
        ["az", *args, "--output", "json", "--only-show-errors"],
        check=False, capture_output=True, text=True,
    )
    if result.returncode:
        raise SystemExit(result.stderr.strip() or "Azure CLI request failed")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def patch_template(resource: dict, template: dict) -> None:
    template.pop("revisionSuffix", None)
    azure(
        "rest", "--method", "patch",
        "--uri", f"{resource['id']}?api-version={api_version}",
        "--headers", "Content-Type=application/json",
        "--body", json.dumps({"properties": {"template": template}}),
    )


group = os.environ["AZURE_RESOURCE_GROUP"]
resource_prefix = (
    f"/subscriptions/{os.environ['AZURE_SUBSCRIPTION_ID']}"
    f"/resourceGroups/{group}/providers/Microsoft.App"
)
app_name = os.environ[f"AZURE_CONTAINER_APP_{service.upper()}_NAME"]
# Read and write the same schema; newer CLI defaults return incompatible fields.
app = azure(
    "rest", "--method", "get",
    "--uri", f"{resource_prefix}/containerApps/{app_name}?api-version={api_version}",
)
template = app["properties"]["template"]
container = next(c for c in template["containers"] if c["name"] == service)
image = container["image"]
registry = os.environ["AZURE_CONTAINER_REGISTRY_ENDPOINT"]
if not image.startswith(f"{registry}/") or image.endswith(":latest"):
    raise SystemExit("Refusing to activate a bootstrap, foreign-registry or latest-tag image")
if "@sha256:" not in image and ":" not in image.rsplit("/", 1)[-1]:
    raise SystemExit("A digest or explicit deployment tag is required")

# Empty command overrides are not reliably cleared by ARM or the Azure CLI.
# Activate the image's entry point explicitly, preserving all other settings.
command = (
    ["supply-chain-routing"] if service == "api"
    else ["/docker-entrypoint.sh", "nginx", "-g", "daemon off;"]
)
if container.get("command") != command:
    container["command"] = command
    patch_template(app, template)

if service == "api":
    job = azure(
        "rest", "--method", "get",
        "--uri", (
            f"{resource_prefix}/jobs/{os.environ['AZURE_CONTAINER_APP_REFRESH_JOB_NAME']}"
            f"?api-version={api_version}"
        ),
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
