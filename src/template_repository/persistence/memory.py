import asyncio
import copy
import time
from typing import Any
from uuid import uuid4

from template_repository.errors import ServiceError
from template_repository.persistence.repository import Document


class MemoryRepository:
    def __init__(self, limit: int = 1000) -> None:
        self._items: dict[tuple[str, str], tuple[Document, float]] = {}
        self._lock = asyncio.Lock()
        self.limit = limit

    def _purge(self) -> None:
        now = time.time()
        self._items = {key: value for key, value in self._items.items() if value[1] > now}

    async def get(self, scenario_id: str, document_id: str) -> Document:
        self._purge()
        item = self._items.get((scenario_id, document_id))
        if item is None:
            raise ServiceError(404, "Document not found or expired.")
        return copy.deepcopy(item[0])

    async def create(self, body: dict[str, Any]) -> Document:
        async with self._lock:
            self._purge()
            key = body["scenario_id"], body["id"]
            if key in self._items:
                raise ServiceError(409, "Document already exists.")
            if len(self._items) >= self.limit:
                raise ServiceError(429, "Demo storage capacity reached; retry after expiration.")
            return self._write(body)

    def _write(self, body: dict[str, Any]) -> Document:
        document = Document(copy.deepcopy(body), f'"{uuid4().hex}"')
        self._items[body["scenario_id"], body["id"]] = (
            document,
            time.time() + body["ttl"],
        )
        return copy.deepcopy(document)

    async def replace(self, body: dict[str, Any], etag: str) -> Document:
        async with self._lock:
            current = await self.get(body["scenario_id"], body["id"])
            if current.etag != etag:
                raise ServiceError(412, "ETag does not match the current document.")
            return self._write(body)

    async def delete(self, scenario_id: str, document_id: str, etag: str) -> None:
        async with self._lock:
            current = await self.get(scenario_id, document_id)
            if current.etag != etag:
                raise ServiceError(412, "ETag does not match the current document.")
            del self._items[scenario_id, document_id]

    async def active_scenarios(self, limit: int, since: float) -> list[Document]:
        self._purge()
        return [
            copy.deepcopy(document)
            for document, _ in self._items.values()
            if document.body["kind"] == "active" and document.body.get("active_at", 0) >= since
        ][:limit]

    async def ready(self) -> None:
        return None

    async def close(self) -> None:
        return None
