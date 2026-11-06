import pytest
from pydantic import ValidationError

from template_repository.config import Settings


class TestConfig:
    def test_default_settings(self) -> None:
        settings = Settings()
        assert settings.log_level == "INFO"
        assert settings.port == 8000
        assert settings.host == "0.0.0.0"

    def test_custom_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("PORT", "9000")
        settings = Settings()
        assert settings.log_level == "DEBUG"
        assert settings.port == 9000


@pytest.mark.parametrize("name,value", [("APP_MODE", "automatic"), ("PORT", "0")])
def test_invalid_runtime_settings(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"entra_tenant_id": "11111111-1111-4111-8111-111111111111"},
        {
            "entra_tenant_id": "common",
            "entra_client_id": "22222222-2222-4222-8222-222222222222",
            "entra_api_scope": "api://routing/access_as_user",
        },
        {
            "entra_tenant_id": "11111111-1111-4111-8111-111111111111",
            "entra_client_id": "not-a-uuid",
            "entra_api_scope": "api://routing/access_as_user",
        },
    ],
)
def test_enabled_authentication_fails_closed_for_incomplete_or_invalid_settings(
    values: dict,
) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, auth_enabled=True, **values)


@pytest.mark.parametrize(
    "scope",
    [
        "access_as_user",
        "api:///access_as_user",
        "api://routing/",
        "http://routing/access_as_user",
        "https://routing/access_as_user?query=1",
        "https://routing/access_as_user#fragment",
        "https://user:password@routing/access_as_user",
        "https://routing:invalid/access_as_user",
        "api://:443/access_as_user",
        "api://routing/access as user",
    ],
)
def test_scope_must_be_fully_qualified(scope: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, entra_api_scope=scope)
