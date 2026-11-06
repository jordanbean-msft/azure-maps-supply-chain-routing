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
