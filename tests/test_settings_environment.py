from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError

from app.core.config import Settings

LIST_ENVIRONMENT = (
    "CORS_ORIGINS",
    "TRUSTED_HOSTS",
    "TRUSTED_PROXY_IPS",
    "PLATFORM_OPERATOR_USER_IDS",
    "FOUNDER_CONTROL_EMAILS",
)


@pytest.fixture(autouse=True)
def _clear_list_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in LIST_ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)


def test_comma_separated_list_environment_matches_documented_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operator = "7b0c1f4e-2c1a-4a55-9a53-0e6b8f7f0a11"
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, http://127.0.0.1:3000")
    monkeypatch.setenv("TRUSTED_HOSTS", "localhost,127.0.0.1,testserver")
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.1")
    monkeypatch.setenv("PLATFORM_OPERATOR_USER_IDS", operator)
    monkeypatch.setenv("FOUNDER_CONTROL_EMAILS", "founder@example.com")

    settings = Settings(_env_file=None)

    assert settings.cors_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    assert settings.trusted_hosts == ["localhost", "127.0.0.1", "testserver"]
    assert settings.trusted_proxy_ips == ["10.0.0.1"]
    assert settings.platform_operator_user_ids == [UUID(operator)]
    assert settings.founder_control_emails == ["founder@example.com"]


def test_json_array_list_environment_remains_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", '["https://app.example.com"]')
    monkeypatch.setenv("TRUSTED_HOSTS", '["api.example.com", "localhost"]')

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["https://app.example.com"]
    assert settings.trusted_hosts == ["api.example.com", "localhost"]


def test_malformed_json_list_environment_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRUSTED_HOSTS", '["api.example.com"')

    with pytest.raises((ValidationError, SettingsError)):
        Settings(_env_file=None)


def test_env_example_file_loads_without_settings_errors() -> None:
    example = Path(__file__).resolve().parents[1] / ".env.example"

    settings = Settings(_env_file=example)

    assert settings.trusted_hosts == ["localhost", "127.0.0.1", "testserver"]
    assert settings.cors_origins == ["http://localhost:3000"]
    assert settings.founder_control_emails == []
