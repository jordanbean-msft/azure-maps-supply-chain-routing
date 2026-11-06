from typing import Protocol


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> None:
        """Raise jwt.InvalidTokenError unless the token grants delegated API access."""
