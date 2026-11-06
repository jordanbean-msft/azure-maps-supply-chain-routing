from collections.abc import AsyncIterator

import httpx
import pytest

from template_repository.app import create_app
from template_repository.config import Settings


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    application = create_app(Settings(_env_file=None, expensive_requests_per_minute=60))
    async with (
        application.router.lifespan_context(application),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application), base_url="http://test"
        ) as session,
    ):
        session.application = application  # type: ignore[attr-defined]
        yield session
