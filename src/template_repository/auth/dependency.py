from typing import cast

import jwt
from fastapi import HTTPException, Request

from template_repository.auth.verifier import TokenVerifier


async def require_authentication(request: Request) -> None:
    if (
        not request.app.state.settings.auth_enabled
        or request.url.path == "/api/auth/config"
        or not (request.url.path == "/api" or request.url.path.startswith("/api/"))
    ):
        return
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and token and not any(char.isspace() for char in token):
        verifier = cast(TokenVerifier, request.app.state.token_verifier)
        try:
            await verifier.verify(token)
            return
        except jwt.InvalidTokenError:
            pass
    raise HTTPException(
        status_code=401,
        detail="A valid delegated bearer token is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
