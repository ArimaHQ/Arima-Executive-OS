"""The production-only privileged MFA gate on Founder Control and Laya/Jarvis."""

import asyncio

import pytest

from app.core.config import Settings
from app.database.repositories import UserRepository
from app.services import permissions
from tests.auth.helpers import bearer, grant_role, login_user, register_user
from tests.management.conftest import management_context

__all__ = ["management_context"]

FOUNDER = "founder@example.com"
PROTECTED = (
    "/api/v1/admin/founder/system-health",
    "/api/v1/admin/founder/brain/status",
    "/api/v1/admin/founder/laya/graph",
    "/api/v1/admin/founder/execution-policy",
)


def production_settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="production",
        jwt_secret_key="p" * 48,
        security_token_secret="q" * 48,
        frontend_url="https://app.example.com",
        cors_origins=["https://app.example.com"],
        trusted_hosts=["api.example.com"],
        auth_cookie_secure=True,
        email_provider="resend",
        resend_api_key="re_production_placeholder",
        email_from_address="noreply@example.com",
        ai_execution_enabled=False,
        founder_control_emails=[FOUNDER],
    )


def test_production_settings_require_privileged_mfa() -> None:
    settings = production_settings()
    assert settings.privileged_mfa_required is True
    assert settings.environment == "production"


def _set_mfa(context, enabled: bool) -> None:
    async def update() -> None:
        async with context.session_factory() as session:
            user = await UserRepository(session).get_by_email(FOUNDER)
            assert user is not None
            user.mfa_enabled = enabled
            await session.commit()

    asyncio.run(update())


def test_founder_surfaces_require_enrolled_mfa_in_production(
    management_context, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = management_context
    register_user(context, FOUNDER)
    grant_role(context, FOUNDER, "administrator")
    headers = bearer(login_user(context, FOUNDER)["access_token"])

    monkeypatch.setattr(permissions, "get_settings", production_settings)
    for path in PROTECTED:
        response = context.client.get(path, headers=headers)
        assert response.status_code == 403, path
        assert response.json()["code"] == "privileged_mfa_enrollment_required", path

    _set_mfa(context, True)
    for path in PROTECTED:
        assert context.client.get(path, headers=headers).status_code == 200, path


def test_development_does_not_apply_the_production_gate(
    management_context, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = management_context
    register_user(context, FOUNDER)
    grant_role(context, FOUNDER, "administrator")
    headers = bearer(login_user(context, FOUNDER)["access_token"])
    development = production_settings().model_copy(update={"environment": "development"})
    monkeypatch.setattr(permissions, "get_settings", lambda: development)
    assert context.client.get(PROTECTED[0], headers=headers).status_code == 200
