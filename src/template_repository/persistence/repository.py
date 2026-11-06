from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Document:
    body: dict[str, Any]
    etag: str


class Repository(Protocol):
    async def get(self, scenario_id: str, document_id: str) -> Document: ...

    async def create(self, body: dict[str, Any]) -> Document: ...

    async def replace(self, body: dict[str, Any], etag: str) -> Document: ...

    async def delete(self, scenario_id: str, document_id: str, etag: str) -> None: ...

    async def active_scenarios(self, limit: int, since: float) -> list[Document]: ...

    async def ready(self) -> None: ...

    async def close(self) -> None: ...
