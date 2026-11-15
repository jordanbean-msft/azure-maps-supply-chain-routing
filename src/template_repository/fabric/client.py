import asyncio
import base64
import json
from typing import Any
from urllib.parse import quote

import httpx
from azure.core.credentials_async import AsyncTokenCredential

FABRIC_API = "https://api.fabric.microsoft.com/v1"
POWERBI_API = "https://api.powerbi.com/v1.0/myorg"


def definition(parts: dict[str, str], format_name: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "parts": [
            {
                "path": path,
                "payload": base64.b64encode(content.encode()).decode(),
                "payloadType": "InlineBase64",
            }
            for path, content in parts.items()
        ]
    }
    if format_name:
        result["format"] = format_name
    return result


class FabricClient:
    def __init__(self, http: httpx.AsyncClient, credential: AsyncTokenCredential) -> None:
        self.http = http
        self.credential = credential

    async def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        powerbi: bool = False,
    ) -> httpx.Response:
        base = POWERBI_API if powerbi else FABRIC_API
        url = path if path.startswith("https://") else f"{base}/{path}"
        allowed = (FABRIC_API + "/", POWERBI_API + "/")
        if not url.startswith(allowed):
            raise ValueError("Unexpected Fabric/Power BI API URL.")
        scope = (
            "https://analysis.windows.net/powerbi/api/.default"
            if powerbi
            else "https://api.fabric.microsoft.com/.default"
        )
        for attempt in range(5):
            token = await self.credential.get_token(scope)
            response = await self.http.request(
                method, url, json=body, headers={"Authorization": f"Bearer {token.token}"}
            )
            if response.status_code == 429 and attempt < 4:
                await asyncio.sleep(int(response.headers.get("Retry-After", "30")))
                continue
            if response.is_error:
                raise RuntimeError(f"Fabric HTTP {response.status_code}: {response.text[:2000]}")
            return response
        raise RuntimeError("Fabric retry budget exhausted.")

    async def complete(
        self, response: httpx.Response, *, has_result: bool = True
    ) -> dict[str, Any]:
        if response.status_code != 202:
            return response.json() if response.content else {}
        operation = response.headers.get("x-ms-operation-id")
        location = (
            f"{FABRIC_API}/operations/{operation}" if operation else response.headers["Location"]
        )
        for _ in range(120):
            await asyncio.sleep(int(response.headers.get("Retry-After", "5")))
            response = await self.request("GET", location)
            result = response.json()
            status = result.get("status")
            if status in {"Failed", "Cancelled"}:
                raise RuntimeError(f"Fabric operation failed: {json.dumps(result)}")
            if status == "Succeeded":
                if not has_result:
                    return {}
                result_response = await self.request("GET", location.rstrip("/") + "/result")
                return result_response.json() if result_response.content else {}
        raise TimeoutError(f"Fabric operation still running: {location}")

    async def items(self, workspace: str) -> list[dict[str, Any]]:
        path = f"workspaces/{workspace}/items"
        values = []
        while path:
            result = (await self.request("GET", path)).json()
            values.extend(result["value"])
            path = result.get("continuationUri")
        return values

    async def publish(
        self,
        workspace: str,
        name: str,
        item_type: str,
        item_definition: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        existing = [
            item
            for item in await self.items(workspace)
            if item["displayName"] == name and item["type"] == item_type
        ]
        if len(existing) > 1:
            raise ValueError(f"Ambiguous item name: {name}")
        if existing:
            item = existing[0]
            if item_definition:
                response = await self.request(
                    "POST",
                    f"workspaces/{workspace}/items/{item['id']}/updateDefinition",
                    {"definition": item_definition},
                )
                await self.complete(response, has_result=False)
            return item
        body: dict[str, Any] = {"displayName": name, "type": item_type}
        if item_definition:
            body["definition"] = item_definition
        return await self.complete(
            await self.request("POST", f"workspaces/{workspace}/items", body)
        )

    async def upload(self, workspace: str, lakehouse: str, name: str, content: bytes) -> None:
        token = await self.credential.get_token("https://storage.azure.com/.default")
        base = f"https://onelake.dfs.fabric.microsoft.com/{workspace}/{lakehouse}/Files"
        headers = {"Authorization": f"Bearer {token.token}", "x-ms-version": "2023-11-03"}
        directory = await self.http.put(
            f"{base}/sample", params={"resource": "directory"}, headers=headers
        )
        if directory.status_code not in {200, 201, 409}:
            raise RuntimeError(f"OneLake directory creation failed: {directory.status_code}")
        url = f"{base}/sample/{quote(name, safe='')}"
        created = await self.http.put(url, params={"resource": "file"}, headers=headers)
        created.raise_for_status()
        appended = await self.http.patch(
            url, params={"action": "append", "position": 0}, content=content, headers=headers
        )
        appended.raise_for_status()
        flushed = await self.http.patch(
            url, params={"action": "flush", "position": len(content)}, headers=headers
        )
        flushed.raise_for_status()

    async def run_notebook(self, workspace: str, notebook: str) -> dict[str, Any]:
        response = await self.request(
            "POST", f"workspaces/{workspace}/items/{notebook}/jobs/RunNotebook/instances"
        )
        location = response.headers["Location"]
        for _ in range(120):
            await asyncio.sleep(int(response.headers.get("Retry-After", "15")))
            response = await self.request("GET", location)
            result = response.json()
            if result["status"] in {"Completed", "Succeeded"}:
                return result
            if result["status"] in {"Failed", "Cancelled", "Deduped"}:
                raise RuntimeError(f"Notebook job failed: {json.dumps(result)}")
        raise TimeoutError(f"Notebook job still running: {location}")
