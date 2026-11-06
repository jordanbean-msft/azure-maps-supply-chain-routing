import jwt

from template_repository.auth.jwks import JwksCache
from template_repository.config import Settings


class EntraTokenVerifier:
    def __init__(self, settings: Settings, keys: JwksCache) -> None:
        self._keys = keys
        self._tenant = str(settings.entra_tenant_id)
        self._audience = str(settings.entra_client_id)
        self._issuer = f"https://login.microsoftonline.com/{self._tenant}/v2.0"
        self._scope = (settings.entra_api_scope or "").rsplit("/", 1)[-1]

    async def verify(self, token: str) -> None:
        # MSAL acquires tokens but does not validate arbitrary API JWTs; PyJWT supplies
        # signature/claim validation while Azure Identity remains the workload credential.
        if not token or len(token) > 16384:
            raise jwt.InvalidTokenError("Invalid token size.")
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if header.get("alg") != "RS256" or not isinstance(kid, str) or not 1 <= len(kid) <= 256:
            raise jwt.InvalidTokenError("Unsupported signing key.")
        key = await self._keys.get_key(kid)
        try:
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={
                    "require": ["exp", "nbf", "iat", "aud", "iss", "tid", "ver", "scp"],
                    "strict_aud": True,
                },
            )
        except (ValueError, TypeError) as error:
            raise jwt.InvalidTokenError("Malformed token claims.") from error
        if (
            claims["tid"] != self._tenant
            or claims["ver"] != "2.0"
            or claims.get("idtyp") == "app"
            or any(type(claims[name]) is not int for name in ("exp", "nbf", "iat"))
            or not isinstance(claims["scp"], str)
            or self._scope not in claims["scp"].split()
        ):
            raise jwt.InvalidTokenError("Token does not grant delegated API access.")
