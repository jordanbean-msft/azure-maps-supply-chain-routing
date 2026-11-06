from unittest.mock import Mock, patch

import pytest

from template_repository.main import main


class TestMain:
    @patch("template_repository.main.uvicorn.run")
    def test_main_starts_uvicorn(self, mock_run: Mock) -> None:
        main()

        mock_run.assert_called_once_with(
            "template_repository.app:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
        )

    @patch("template_repository.main.uvicorn.run")
    def test_main_uses_custom_settings(
        self, mock_run: Mock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PORT", "9000")
        monkeypatch.setenv("HOST", "127.0.0.1")

        main()

        mock_run.assert_called_once_with(
            "template_repository.app:app",
            host="127.0.0.1",
            port=9000,
            reload=True,
        )

    @patch("template_repository.main.uvicorn.run")
    def test_production_does_not_reload(
        self, mock_run: Mock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AZURE_ENVIRONMENT", "production")
        main()
        assert mock_run.call_args.kwargs["reload"] is False
