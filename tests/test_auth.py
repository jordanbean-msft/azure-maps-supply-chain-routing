import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, tzinfo

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.routing import APIRoute
from jwt.algorithms import RSAAlgorithm

from template_repository.app import create_app
from template_repository.auth.entra import EntraTokenVerifier
from template_repository.auth.jwks import JwksCache
from template_repository.config import Settings
from tests.test_workflows import completed

TENANT = "11111111-1111-4111-8111-111111111111"
CLIENT = "22222222-2222-4222-8222-222222222222"
SCOPE = f"api://{CLIENT}/access_as_user"
NOW = 2_000_000_000


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz: tzinfo | None = None) -> datetime:
        return datetime.fromtimestamp(NOW, tz or UTC)


@pytest.fixture(autouse=True)
def fixed_token_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jwt.api_jwt, "datetime", FixedDatetime)


@pytest.fixture(scope="module")
def private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def jwk(private_key: rsa.RSAPrivateKey) -> dict:
    return {**json.loads(RSAAlgorithm.to_jwk(private_key.public_key())), "kid": "signing-key"}


@pytest.fixture
def auth_settings() -> Settings:
    return Settings(
        _env_file=None,
        auth_enabled=True,
        entra_tenant_id=TENANT,
        entra_client_id=CLIENT,
        entra_api_scope=SCOPE,
        requests_per_minute=1000,
        expensive_requests_per_minute=60,
    )


@pytest.fixture
def claims() -> dict:
    return {
        "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0",
        "aud": CLIENT,
        "tid": TENANT,
        "ver": "2.0",
        "iat": NOW - 60,
        "nbf": NOW - 60,
        "exp": NOW + 600,
        "scp": "other_scope access_as_user",
        "sub": "tenant-user",
    }


def signed_token(private_key: rsa.RSAPrivateKey, claims: dict, **headers: str) -> str:
    return jwt.encode(
        claims, private_key, algorithm="RS256", headers={"kid": "signing-key", **headers}
    )


@pytest.fixture
async def verifier(auth_settings: Settings, jwk: dict) -> AsyncIterator[EntraTokenVerifier]:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == (
            f"https://login.microsoftonline.com/{TENANT}/discovery/v2.0/keys"
        )
        return httpx.Response(200, json={"keys": [jwk]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        yield EntraTokenVerifier(auth_settings, JwksCache(client, TENANT))


@pytest.fixture
async def auth_client(
    auth_settings: Settings, verifier: EntraTokenVerifier
) -> AsyncIterator[httpx.AsyncClient]:
    application = create_app(auth_settings, token_verifier=verifier)
    async with (
        application.router.lifespan_context(application),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application), base_url="http://test"
        ) as client,
    ):
        client.application = application  # type: ignore[attr-defined]
        yield client


async def test_valid_delegated_token_ignores_untrusted_key_urls(
    verifier: EntraTokenVerifier, private_key: rsa.RSAPrivateKey, claims: dict
) -> None:
    await verifier.verify(
        signed_token(
            private_key,
            claims,
            jku="https://attacker.invalid/keys",
            x5u="https://attacker.invalid/certificate",
        )
    )


@pytest.mark.parametrize(
    "name,value",
    [
        ("exp", NOW),
        ("nbf", NOW + 1),
        ("iat", NOW + 1),
        ("exp", [NOW + 600]),
        ("iat", True),
        ("nbf", str(NOW - 60)),
        ("aud", f"api://{CLIENT}"),
        ("aud", [CLIENT]),
        ("aud", TENANT),
        ("tid", CLIENT),
        ("ver", "1.0"),
        ("iss", f"https://sts.windows.net/{TENANT}/"),
        ("iss", f"https://login.microsoftonline.com/{CLIENT}/v2.0"),
        ("iss", f"https://login.microsoftonline.com/{TENANT}/v2.0/"),
        ("scp", "access_as_user_extra"),
        ("scp", ["access_as_user"]),
        ("scp", ""),
        ("idtyp", "app"),
    ],
)
async def test_rejects_invalid_claims(
    verifier: EntraTokenVerifier,
    private_key: rsa.RSAPrivateKey,
    claims: dict,
    name: str,
    value: object,
) -> None:
    claims[name] = value
    with pytest.raises(jwt.InvalidTokenError):
        await verifier.verify(signed_token(private_key, claims))


@pytest.mark.parametrize("name", ["exp", "nbf", "iat", "aud", "iss", "tid", "ver", "scp"])
async def test_requires_claims(
    verifier: EntraTokenVerifier, private_key: rsa.RSAPrivateKey, claims: dict, name: str
) -> None:
    del claims[name]
    claims["roles"] = ["access_as_user"]
    with pytest.raises(jwt.InvalidTokenError):
        await verifier.verify(signed_token(private_key, claims))


@pytest.mark.parametrize("algorithm", ["none", "HS256"])
async def test_rejects_other_algorithms(
    verifier: EntraTokenVerifier, claims: dict, algorithm: str
) -> None:
    key = "" if algorithm == "none" else "not-a-public-key" * 4
    token = jwt.encode(claims, key, algorithm=algorithm, headers={"kid": "signing-key"})
    with pytest.raises(jwt.InvalidTokenError):
        await verifier.verify(token)


async def test_rejects_invalid_signature(verifier: EntraTokenVerifier, claims: dict) -> None:
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(jwt.InvalidSignatureError):
        await verifier.verify(signed_token(other_key, claims))


@pytest.mark.parametrize("token", ["not-a-jwt", "", "a" * 16385])
async def test_rejects_malformed_tokens(verifier: EntraTokenVerifier, token: str) -> None:
    with pytest.raises(jwt.InvalidTokenError):
        await verifier.verify(token)


async def test_requires_key_identifier(
    verifier: EntraTokenVerifier, private_key: rsa.RSAPrivateKey, claims: dict
) -> None:
    with pytest.raises(jwt.InvalidTokenError):
        await verifier.verify(jwt.encode(claims, private_key, algorithm="RS256"))


async def test_jwks_cache_bounds_concurrent_refresh_rotation_and_staleness(jwk: dict) -> None:
    now = [0.0]
    requests = []
    document = {"keys": [jwk]}

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        await asyncio.sleep(0)
        return httpx.Response(200, json=document)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        cache = JwksCache(client, TENANT, clock=lambda: now[0])
        await asyncio.gather(*(cache.get_key("signing-key") for _ in range(10)))
        assert len(requests) == 1
        failures = await asyncio.gather(
            *(cache.get_key(f"unknown-{index}") for index in range(10)), return_exceptions=True
        )
        assert all(isinstance(error, jwt.InvalidTokenError) for error in failures)
        assert len(requests) == 1
        now[0] = 31
        document["keys"] = [{**jwk, "kid": "rotated-key"}]
        await asyncio.gather(*(cache.get_key("rotated-key") for _ in range(10)))
        assert len(requests) == 2
        with pytest.raises(jwt.InvalidTokenError):
            await cache.get_key("signing-key")
        # Expired keys cannot be used when refresh fails; failure also starts cooldown.
        now[0] += 3601
        document["keys"] = []
        with pytest.raises(jwt.InvalidTokenError):
            await cache.get_key("rotated-key")
        with pytest.raises(jwt.InvalidTokenError):
            await cache.get_key("rotated-key")
        assert len(requests) == 3


@pytest.mark.parametrize(
    "body",
    [
        b"not-json",
        b"[]",
        b"{}",
        b'{"keys": []}',
        b'{"keys": [null]}',
        b'{"keys": [{"kty": "RSA", "kid": "a", "key_ops": null}]}',
        b'{"keys": [{"kty": "RSA", "kid": "a", "n": "bad", "e": "bad"}]}',
        b'{"keys": [{"kty": "oct", "kid": "a"}]}',
        b'{"keys": ' + json.dumps([{}] * 33).encode() + b"}",
        b"a" * 131073,
    ],
)
async def test_jwks_rejects_malformed_or_oversized_documents(body: bytes) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=body))
    ) as client:
        with pytest.raises(jwt.InvalidTokenError):
            await JwksCache(client, TENANT).get_key("a")


@pytest.mark.parametrize("failure", ["http", "timeout", "redirect"])
async def test_jwks_failure_is_closed_and_throttled(failure: str) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("offline", request=request)
        return httpx.Response(
            302 if failure == "redirect" else 503,
            headers={"Location": "https://attacker.invalid/keys"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        cache = JwksCache(client, TENANT)
        for _ in range(2):
            with pytest.raises(jwt.InvalidTokenError):
                await cache.get_key("a")
        assert len(requests) == 1


async def test_every_registered_api_operation_requires_bearer(
    auth_client: httpx.AsyncClient,
) -> None:
    application = auth_client.application  # type: ignore[attr-defined]
    protected = 0
    for route in application.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/"):
            continue
        if route.path == "/api/auth/config":
            continue
        path = route.path.format(
            scenario_id="example", run_id="run", route_id="route", disruption_id="disruption"
        )
        for method in sorted(route.methods):
            response = await auth_client.request(method, path)
            assert response.status_code == 401, (method, path, response.text)
            assert response.headers["WWW-Authenticate"] == "Bearer"
            assert response.headers["content-type"] == "application/problem+json"
            protected += 1
    assert protected >= 15


async def test_discovery_and_health_are_public(auth_client: httpx.AsyncClient) -> None:
    response = await auth_client.get("/api/auth/config")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "enabled": True,
        "tenant_id": TENANT,
        "client_id": CLIENT,
        "scope": SCOPE,
    }
    for path in ["/health", "/health/live", "/health/ready"]:
        assert (await auth_client.get(path)).status_code == 200


async def test_disabled_demo_remains_anonymous(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/auth/config")).json() == {
        "enabled": False,
        "tenant_id": None,
        "client_id": None,
        "scope": None,
    }
    assert (await client.get("/api/config")).status_code == 200


@pytest.mark.parametrize("authorization", ["", "Basic credentials", "Bearer invalid", "Bearer a b"])
async def test_proxy_headers_and_url_tokens_never_authenticate(
    auth_client: httpx.AsyncClient,
    private_key: rsa.RSAPrivateKey,
    claims: dict,
    authorization: str,
) -> None:
    token = signed_token(private_key, claims)
    response = await auth_client.get(
        "/api/config",
        params={"access_token": token},
        headers={
            "Authorization": authorization,
            "X-MS-CLIENT-PRINCIPAL": token,
            "X-MS-TOKEN-AAD-ACCESS-TOKEN": token,
        },
    )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_api_checks_signature_not_just_claims(
    auth_client: httpx.AsyncClient, claims: dict
) -> None:
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    response = await auth_client.get(
        "/api/config", headers={"Authorization": f"Bearer {signed_token(other_key, claims)}"}
    )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_signed_access_supports_shared_scenarios_maps_and_sse(
    auth_client: httpx.AsyncClient, private_key: rsa.RSAPrivateKey, claims: dict
) -> None:
    auth_client.headers["Authorization"] = f"Bearer {signed_token(private_key, claims)}"
    assert (await auth_client.get("/api/config")).status_code == 200
    # Authorized requests reach the Maps endpoint, which has no demo browser identity.
    assert (await auth_client.get("/api/maps/token")).status_code == 503
    seed = await auth_client.post("/api/scenarios/seed")
    assert seed.status_code == 201
    path = seed.headers["location"]
    claims["sub"] = "another-user-in-the-same-tenant"
    auth_client.headers["Authorization"] = f"Bearer {signed_token(private_key, claims)}"
    assert (await auth_client.get(path)).status_code == 200
    submitted = await auth_client.post(path + "/optimize")
    assert submitted.status_code == 202
    run_path = submitted.headers["location"]
    assert (await completed(auth_client, run_path))["status"] == "completed"
    response = await auth_client.get(run_path + "/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"status": "completed"' in response.text
    auth_client.headers.pop("Authorization")
    assert (await auth_client.get(run_path + "/events")).status_code == 401
