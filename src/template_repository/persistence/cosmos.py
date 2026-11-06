from collections.abc import Mapping
from typing import Any

from azure.core import MatchConditions
from azure.core.exceptions import AzureError
from azure.cosmos.aio import ContainerProxy

from template_repository.errors import ServiceError
from template_repository.persistence.repository import Document
from template_repository.telemetry import cosmos_charge


def _observe(headers: Mapping[str, str], response: Any) -> None:
    charge = headers.get("x-ms-request-charge")
    if charge:
        cosmos_charge.add(float(charge))


class CosmosRepository:
    """One pre-provisioned container, /scenario_id partition key, per-document TTL."""

    def __init__(self, container: ContainerProxy) -> None:
        self.container = container

    @staticmethod
    def _document(value: dict[str, Any]) -> Document:
        return Document({k: v for k, v in value.items() if not k.startswith("_")}, value["_etag"])

    @staticmethod
    def _error(error: AzureError) -> ServiceError:
        status = getattr(error, "status_code", None) or 503
        return ServiceError(
            status if status in (404, 409, 412, 429) else 503,
            {
                404: "Document not found or expired.",
                409: "Document already exists.",
                412: "ETag does not match the current document.",
                429: "Persistence request budget exceeded.",
            }.get(status, "Persistence service unavailable."),
        )

    async def get(self, scenario_id: str, document_id: str) -> Document:
        try:
            return self._document(
                await self.container.read_item(
                    document_id, partition_key=scenario_id, response_hook=_observe
                )
            )
        except AzureError as error:
            raise self._error(error) from error

    async def create(self, body: dict[str, Any]) -> Document:
        try:
            # create/replace derive the partition key from the body, not a query.
            return self._document(await self.container.create_item(body, response_hook=_observe))
        except AzureError as error:
            raise self._error(error) from error

    async def replace(self, body: dict[str, Any], etag: str) -> Document:
        try:
            return self._document(
                await self.container.replace_item(
                    body["id"],
                    body,
                    etag=etag,
                    match_condition=MatchConditions.IfNotModified,
                    response_hook=_observe,
                )
            )
        except AzureError as error:
            raise self._error(error) from error

    async def delete(self, scenario_id: str, document_id: str, etag: str) -> None:
        try:
            await self.container.delete_item(
                document_id,
                partition_key=scenario_id,
                etag=etag,
                match_condition=MatchConditions.IfNotModified,
                response_hook=_observe,
            )
        except AzureError as error:
            raise self._error(error) from error

    async def active_scenarios(self, limit: int, since: float) -> list[Document]:
        try:
            values = self.container.query_items(
                query="SELECT TOP @limit * FROM c WHERE c.kind = 'active' AND c.active_at >= @since",
                parameters=[
                    {"name": "@limit", "value": limit},
                    {"name": "@since", "value": since},
                ],
                max_item_count=limit,
                response_hook=_observe,
            )
            return [self._document(value) async for value in values]
        except AzureError as error:
            raise self._error(error) from error

    async def ready(self) -> None:
        try:
            properties = await self.container.read()
            if properties.get("partitionKey", {}).get("paths") != ["/scenario_id"]:
                raise ServiceError(503, "Cosmos container requires /scenario_id partition key.")
            if properties.get("defaultTtl") is None:
                raise ServiceError(503, "Cosmos container TTL must be enabled.")
        except AzureError as error:
            raise self._error(error) from error

    async def close(self) -> None:
        return None
