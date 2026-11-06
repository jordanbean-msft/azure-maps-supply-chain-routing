import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from azure.core import MatchConditions
from azure.cosmos.exceptions import CosmosHttpResponseError

from template_repository.errors import ServiceError
from template_repository.persistence.cosmos import CosmosRepository, _observe
from template_repository.persistence.memory import MemoryRepository


async def test_memory_atomic_etags_expiration_partition_and_capacity() -> None:
    repository = MemoryRepository(limit=2)
    body = {"id": "same", "scenario_id": "one", "kind": "scenario", "ttl": 60}
    original = await repository.create(body)
    original.body["kind"] = "modified-copy"
    assert (await repository.get("one", "same")).body["kind"] == "scenario"
    two = await repository.create(dict(body, scenario_id="two"))
    assert two.etag != original.etag
    with pytest.raises(ServiceError, match="already exists"):
        await repository.create(body)
    with pytest.raises(ServiceError, match="capacity"):
        await repository.create(dict(body, id="other"))
    results = await asyncio.gather(
        repository.replace(body, original.etag),
        repository.replace(body, original.etag),
        return_exceptions=True,
    )
    assert sum(isinstance(value, ServiceError) and value.status == 412 for value in results) == 1
    with pytest.raises(ServiceError, match="ETag"):
        await repository.delete("two", "same", '"stale"')
    await repository.delete("two", "same", two.etag)
    with (
        patch("template_repository.persistence.memory.time.time", return_value=time.time() + 61),
        pytest.raises(ServiceError, match="expired"),
    ):
        await repository.get("one", "same")
    await repository.ready()
    await repository.close()


async def test_cosmos_serialization_partition_and_conditional_writes() -> None:
    body = {
        "id": "s",
        "scenario_id": "s",
        "kind": "scenario",
        "ttl": 3600,
        "scenario": {"name": "Seattle"},
    }
    value = dict(body, _etag='"etag"', _rid="internal")
    container = MagicMock()
    for name in ("read_item", "create_item", "replace_item"):
        getattr(container, name).return_value = value
        setattr(container, name, AsyncMock(return_value=value))
    container.delete_item = AsyncMock()
    container.read = AsyncMock(
        return_value={"partitionKey": {"paths": ["/scenario_id"]}, "defaultTtl": -1}
    )
    repository = CosmosRepository(container)
    read = await repository.get("s", "s")
    assert read.body == body and read.etag == '"etag"'
    container.read_item.assert_awaited_once_with("s", partition_key="s", response_hook=_observe)
    assert (await repository.create(body)).body["ttl"] == 3600
    await repository.replace(body, read.etag)
    container.replace_item.assert_awaited_once_with(
        "s",
        body,
        etag='"etag"',
        match_condition=MatchConditions.IfNotModified,
        response_hook=_observe,
    )
    await repository.delete("s", "s", read.etag)
    container.delete_item.assert_awaited_once_with(
        "s",
        partition_key="s",
        etag='"etag"',
        match_condition=MatchConditions.IfNotModified,
        response_hook=_observe,
    )
    await repository.ready()
    await repository.close()


@pytest.mark.parametrize("operation", ["get", "create", "replace", "delete", "ready"])
@pytest.mark.parametrize("status", [404, 409, 412, 429, 500])
async def test_cosmos_translates_failures_without_leaking_payload(
    operation: str, status: int
) -> None:
    container = MagicMock()
    error = CosmosHttpResponseError(status_code=status, message="secret upstream payload")
    for name in ("read_item", "create_item", "replace_item", "delete_item", "read"):
        setattr(container, name, AsyncMock(side_effect=error))
    repository = CosmosRepository(container)
    args = {
        "get": ("s", "doc"),
        "create": ({"id": "doc"},),
        "replace": ({"id": "doc"}, '"etag"'),
        "delete": ("s", "doc", '"etag"'),
        "ready": (),
    }
    with pytest.raises(ServiceError) as caught:
        await getattr(repository, operation)(*args[operation])
    assert caught.value.status == (503 if status == 500 else status)
    assert "secret" not in caught.value.detail


async def test_cosmos_active_scan_is_bounded_and_container_schema_validated() -> None:
    container = MagicMock()

    async def items():
        yield {"id": "active", "scenario_id": "s", "kind": "active", "_etag": '"e"'}

    container.query_items.return_value = items()
    repository = CosmosRepository(container)
    values = await repository.active_scenarios(3, 100)
    assert values[0].body["scenario_id"] == "s"
    query = container.query_items.call_args.kwargs
    assert query["parameters"] == [{"name": "@limit", "value": 3}, {"name": "@since", "value": 100}]
    assert query["max_item_count"] == 3
    container.read = AsyncMock(return_value={"partitionKey": {"paths": ["/wrong"]}})
    with pytest.raises(ServiceError, match="partition"):
        await repository.ready()
    container.read.return_value = {"partitionKey": {"paths": ["/scenario_id"]}}
    with pytest.raises(ServiceError, match="TTL"):
        await repository.ready()
