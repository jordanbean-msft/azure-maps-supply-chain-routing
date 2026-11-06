#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/../.."

python3 - <<'PY'
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

source = Path("infra/scripts/deploy-refresh.sh").read_text().split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
environment = {
    "AZURE_SUBSCRIPTION_ID": "test-subscription",
    "AZURE_RESOURCE_GROUP": "existing-rg",
    "AZURE_CONTAINER_APP_API_NAME": "api",
    "AZURE_CONTAINER_APP_WEB_NAME": "web",
    "AZURE_CONTAINER_APP_REFRESH_JOB_NAME": "refresh",
    "AZURE_CONTAINER_REGISTRY_ENDPOINT": "demo.azurecr.io",
}


class HookTests(unittest.TestCase):
    def invoke(self, service: str, image: str, command: list | None = None) -> list:
        patches = []
        app = {
            "id": f"/apps/{service}",
            "properties": {"template": {
                "revisionSuffix": "old-revision",
                "containers": [{
                    "name": service, "image": image,
                    "command": command if command is not None else ["python", "-c", "bootstrap"],
                    "env": [{"name": "AZURE_CLIENT_ID", "value": "api-identity"}],
                    "probes": [{"type": "Readiness"}],
                }],
            }},
        }
        job = {
            "id": "/jobs/refresh",
            "properties": {"template": {"containers": [{
                "name": "refresh", "image": "bootstrap", "command": ["python", "-m", "template_repository.refresh"],
                "env": [{"name": "AZURE_CLIENT_ID", "value": "refresh-identity"}],
                "resources": {"cpu": 0.5, "memory": "1Gi"},
            }]}},
        }

        def fake_azure(args: list, **kwargs: object) -> subprocess.CompletedProcess:
            self.assertEqual(args[1:3], ["rest", "--method"])
            uri = args[args.index("--uri") + 1]
            self.assertTrue(uri.endswith("?api-version=2025-01-01"))
            if args[3] == "get" and "/containerApps/" in uri:
                result = copy.deepcopy(app)
            elif args[3] == "get" and "/jobs/" in uri:
                result = copy.deepcopy(job)
            elif args[3] == "patch":
                patches.append((args[args.index("--uri") + 1], json.loads(args[args.index("--body") + 1])))
                result = {}
            else:
                raise AssertionError(f"Unexpected Azure command: {args[:4]}")
            return subprocess.CompletedProcess(args, 0, json.dumps(result), "")

        with patch.dict(os.environ, environment), patch.object(sys, "argv", ["hook", service]), patch(
            "subprocess.run", side_effect=fake_azure
        ), patch("sys.stdout", new_callable=io.StringIO):
            exec(compile(source, "deploy-refresh.sh", "exec"), {})
        return patches

    def test_api_synchronizes_exact_image_preserving_refresh_identity(self) -> None:
        image = "demo.azurecr.io/api:deployment-20261106"
        patches = self.invoke("api", image)
        self.assertEqual(len(patches), 2)
        api_template = patches[0][1]["properties"]["template"]
        self.assertNotIn("revisionSuffix", api_template)
        self.assertEqual(api_template["containers"][0]["command"], ["supply-chain-routing"])
        self.assertEqual(api_template["containers"][0]["probes"], [{"type": "Readiness"}])
        job_container = patches[1][1]["properties"]["template"]["containers"][0]
        self.assertEqual(job_container["image"], image)
        self.assertEqual(job_container["command"], ["python", "-m", "template_repository.refresh"])
        self.assertEqual(job_container["env"][0]["value"], "refresh-identity")
        self.assertEqual(job_container["resources"], {"cpu": 0.5, "memory": "1Gi"})

    def test_web_does_not_modify_refresh_job(self) -> None:
        patches = self.invoke("web", "demo.azurecr.io/web@sha256:abc123")
        self.assertEqual(len(patches), 1)
        self.assertEqual(
            patches[0][1]["properties"]["template"]["containers"][0]["command"],
            ["/docker-entrypoint.sh", "nginx", "-g", "daemon off;"],
        )

    def test_already_activated_web_command_is_not_updated(self) -> None:
        patches = self.invoke(
            "web", "demo.azurecr.io/web:v1",
            command=["/docker-entrypoint.sh", "nginx", "-g", "daemon off;"],
        )
        self.assertEqual(patches, [])

    def test_rejects_mutable_or_foreign_images(self) -> None:
        for image in ["demo.azurecr.io/api:latest", "demo.azurecr.io/api", "foreign.azurecr.io/api:v1"]:
            with self.subTest(image=image), self.assertRaises(SystemExit):
                self.invoke("api", image)

    def test_reports_azure_failure_without_dumping_request_arguments(self) -> None:
        with patch.dict(os.environ, environment), patch.object(sys, "argv", ["hook", "api"]), patch(
            "subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "Azure rejected the request")
        ), self.assertRaisesRegex(SystemExit, "^Azure rejected the request$"):
            exec(compile(source, "deploy-refresh.sh", "exec"), {})


unittest.main()
PY
