import asyncio
import json
import time
from collections.abc import Callable

import httpx
import jwt

_MAX_KEYS = 32
_MAX_BYTES = 131072
_CACHE_SECONDS = 3600
_REFRESH_COOLDOWN_SECONDS = 30


class JwksCache:
    """Bounded tenant-only key cache; concurrent and unknown-kid refreshes are throttled."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        tenant_id: str,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        self._clock = clock
        self._keys: dict[str, jwt.PyJWK] = {}
        self._expires_at = float("-inf")
        self._next_refresh = float("-inf")
        self._lock = asyncio.Lock()

    async def get_key(self, kid: str) -> jwt.PyJWK:
        now = self._clock()
        if now < self._expires_at and kid in self._keys:
            return self._keys[kid]
        async with self._lock:
            now = self._clock()
            if now < self._expires_at and kid in self._keys:
                return self._keys[kid]
            if now >= self._next_refresh:
                self._next_refresh = now + _REFRESH_COOLDOWN_SECONDS
                try:
                    keys = await self._fetch()
                except (httpx.HTTPError, ValueError, TypeError, jwt.PyJWTError) as error:
                    raise jwt.InvalidTokenError("Signing keys unavailable.") from error
                self._keys = keys
                self._expires_at = self._clock() + _CACHE_SECONDS
            if self._clock() >= self._expires_at or kid not in self._keys:
                raise jwt.InvalidTokenError("Signing key unavailable.")
            return self._keys[kid]

    async def _fetch(self) -> dict[str, jwt.PyJWK]:
        body = bytearray()
        async with self._client.stream(
            "GET", self._url, timeout=10, follow_redirects=False
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > _MAX_BYTES:
                    raise ValueError("JWKS response is too large.")
        document = json.loads(body)
        if not isinstance(document, dict):
            raise ValueError("Invalid JWKS document.")
        entries = document.get("keys")
        if not isinstance(entries, list) or not 1 <= len(entries) <= _MAX_KEYS:
            raise ValueError("Invalid JWKS key count.")
        keys: dict[str, jwt.PyJWK] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("Invalid JWK.")
            operations = entry.get("key_ops", ["verify"])
            if not isinstance(operations, list):
                raise ValueError("Invalid JWK operations.")
            if (
                entry.get("kty") != "RSA"
                or entry.get("use", "sig") != "sig"
                or entry.get("alg", "RS256") != "RS256"
                or "verify" not in operations
            ):
                continue
            kid = entry.get("kid")
            if not isinstance(kid, str) or not 1 <= len(kid) <= 256 or kid in keys:
                raise ValueError("Invalid or duplicate signing key identifier.")
            keys[kid] = jwt.PyJWK.from_dict(entry, algorithm="RS256")
        if not keys:
            raise ValueError("No supported signing keys.")
        return keys
