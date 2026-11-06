from pydantic import BaseModel


class AuthConfig(BaseModel):
    enabled: bool
    tenant_id: str | None
    client_id: str | None
    scope: str | None
