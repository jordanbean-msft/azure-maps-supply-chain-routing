import asyncio
from contextlib import AsyncExitStack

import httpx
from azure.core.credentials_async import AsyncTokenCredential
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential, ManagedIdentityCredential

from template_repository.config import Settings
from template_repository.errors import ServiceError
from template_repository.persistence.cosmos import CosmosRepository
from template_repository.persistence.memory import MemoryRepository
from template_repository.persistence.repository import Repository
from template_repository.routing.azure_maps import AzureMapsRouting
from template_repository.routing.provider import RoutingProvider
from template_repository.routing.simulated import SimulatedRouting
from template_repository.services.runs import RunService
from template_repository.services.scenarios import ScenarioService


class Runtime:
    def __init__(
        self,
        settings: Settings,
        repository: Repository | None = None,
        routing: RoutingProvider | None = None,
    ) -> None:
        self.settings = settings
        self.stack = AsyncExitStack()
        self.repository = repository or MemoryRepository(settings.max_memory_documents)
        self.routing = routing or SimulatedRouting()
        self.injected = repository is not None and routing is not None
        self.initialized = settings.app_mode == "demo" or self.injected
        self.browser_credential: AsyncTokenCredential | None = None
        self.runs = RunService(self.repository, self.routing, settings)
        self.scenarios = ScenarioService(self.repository, settings)

    async def start(self) -> None:
        if self.settings.app_mode == "live" and not self.injected:
            if not self.settings.cosmos_endpoint or not self.settings.azure_maps_client_id:
                raise ServiceError(503, "Live Cosmos and Azure Maps settings are required.")
            credential: AsyncTokenCredential
            if self.settings.allow_developer_credentials:
                credential = DefaultAzureCredential(
                    managed_identity_client_id=self.settings.azure_client_id
                )
            else:
                credential = ManagedIdentityCredential(client_id=self.settings.azure_client_id)
            self.stack.push_async_callback(credential.close)
            async with asyncio.timeout(10):
                await credential.get_token("https://atlas.microsoft.com/.default")
            cosmos = await self.stack.enter_async_context(
                CosmosClient(
                    self.settings.cosmos_endpoint,
                    credential=credential,
                    connection_timeout=5,
                    retry_total=2,
                )
            )
            container = cosmos.get_database_client(
                self.settings.cosmos_database
            ).get_container_client(self.settings.cosmos_container)
            self.repository = CosmosRepository(container)
            http = await self.stack.enter_async_context(
                httpx.AsyncClient(timeout=8, limits=httpx.Limits(max_connections=8))
            )
            self.routing = AzureMapsRouting(http, credential, self.settings, self.repository)
            # Never expose the backend identity's routing/search permissions to a browser.
            # Infra must give this separate identity render-only Azure Maps data actions.
            if self.settings.maps_browser_client_id:
                self.browser_credential = ManagedIdentityCredential(
                    client_id=self.settings.maps_browser_client_id
                )
                self.stack.push_async_callback(self.browser_credential.close)
            self.runs = RunService(self.repository, self.routing, self.settings)
            self.scenarios = ScenarioService(self.repository, self.settings)
        await self.repository.ready()
        self.initialized = True

    def require_ready(self) -> None:
        if not self.initialized:
            raise ServiceError(503, "Live dependencies are not initialized.")

    async def close(self) -> None:
        await self.runs.close()
        await self.repository.close()
        await self.stack.aclose()
        self.initialized = False
