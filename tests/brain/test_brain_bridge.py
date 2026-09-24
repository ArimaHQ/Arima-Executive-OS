"""Unit tests for the Executive OS → Node Brain bridge.

These tests never call the real Brain. They use ``httpx.MockTransport`` to
verify:

* Fail-closed defaults (disabled, unconfigured).
* Transport failure and timeout mapping.
* Success envelope forwarding with data + provenance intact.
* Upstream error envelope propagation.
* Public status route does not leak credentials.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from pydantic import SecretStr

from app.core.config import Settings
from app.services.brain_bridge import BrainBridge


def _enabled_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "brain_internal_enabled": True,
        "brain_internal_url": "http://brain.internal.test",
        "brain_internal_credential_id": "executive-os-test",
        "brain_internal_credential_secret": SecretStr("bridge-test-secret"),
        "brain_internal_timeout_seconds": 2.0,
        "brain_internal_contract_version": "brain.internal.v1",
    }
    base.update(overrides)
    return Settings(**base)


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def test_bridge_disabled_returns_brain_unavailable():
    async def exercise():
        settings = Settings(brain_internal_enabled=False)
        bridge = BrainBridge(settings)
        return await bridge.call(
            "GET", "/brain/v1/capabilities", capability="capabilities"
        )

    response = asyncio.run(exercise())
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "BRAIN_UNAVAILABLE"
    assert response.status == "BRAIN_UNAVAILABLE"
    assert response.execution_authority == "NONE"
    assert response.error.details["reason"] == "BRAIN_INTERNAL_ENABLED=false"


def test_bridge_missing_credentials_fails_closed():
    async def exercise():
        settings = Settings(
            brain_internal_enabled=True,
            brain_internal_url="http://brain.internal.test",
        )
        bridge = BrainBridge(settings)
        return await bridge.call(
            "GET", "/brain/v1/context", capability="context"
        )

    response = asyncio.run(exercise())
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "BRAIN_UNAVAILABLE"
    assert response.error.details["reason"] == "MISSING_CREDENTIAL_OR_URL"


def test_bridge_forwards_success_envelope():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            json={
                "ok": True,
                "contractVersion": "brain.internal.v1",
                "requestId": "brain-req-1",
                "correlationId": "brain-corr-1",
                "status": "READY",
                "executionAuthority": "NONE",
                "data": {"capabilities": [{"id": "context"}]},
                "provenance": {"tenantId": "t1", "workspaceId": "w1"},
            },
        )

    async def exercise():
        bridge = BrainBridge(
            _enabled_settings(), transport=_mock_transport(handler)
        )
        return await bridge.call(
            "GET",
            "/brain/v1/capabilities",
            capability="capabilities",
            user_id="user-1",
        )

    response = asyncio.run(exercise())
    assert response.ok is True
    assert response.data == {"capabilities": [{"id": "context"}]}
    assert response.provenance == {"tenantId": "t1", "workspaceId": "w1"}
    assert response.status == "READY"
    assert response.execution_authority == "NONE"

    headers = captured["headers"]
    assert headers["authorization"] == "Bearer bridge-test-secret"
    assert headers["x-contract-version"] == "brain.internal.v1"
    assert headers["x-correlation-id"]
    assert captured["url"].endswith("/brain/v1/capabilities")


def test_bridge_maps_upstream_error_envelope():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "ok": False,
                "contractVersion": "brain.internal.v1",
                "requestId": "brain-req-2",
                "correlationId": "brain-corr-2",
                "error": {
                    "code": "ROLE_FORBIDDEN",
                    "message": "Write role required",
                    "retryable": False,
                    "details": {"required": "manager"},
                },
                "executionAuthority": "NONE",
            },
        )

    async def exercise():
        bridge = BrainBridge(
            _enabled_settings(), transport=_mock_transport(handler)
        )
        return await bridge.call(
            "GET", "/brain/v1/context", capability="context"
        )

    response = asyncio.run(exercise())
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "ROLE_FORBIDDEN"
    assert response.error.details["required"] == "manager"


def test_bridge_maps_transport_error_to_brain_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    async def exercise():
        bridge = BrainBridge(
            _enabled_settings(), transport=_mock_transport(handler)
        )
        return await bridge.call(
            "GET", "/brain/v1/capabilities", capability="capabilities"
        )

    response = asyncio.run(exercise())
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "BRAIN_UNAVAILABLE"
    assert response.error.retryable is True
    assert response.error.details["reason"] == "TRANSPORT_ERROR"


def test_bridge_maps_5xx_to_brain_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    async def exercise():
        bridge = BrainBridge(
            _enabled_settings(), transport=_mock_transport(handler)
        )
        return await bridge.call(
            "GET", "/brain/v1/context", capability="context"
        )

    response = asyncio.run(exercise())
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "BRAIN_UNAVAILABLE"
    assert response.error.details["reason"] == "UPSTREAM_5XX"
    assert response.error.details["status"] == 503


def test_bridge_maps_malformed_json_to_brain_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    async def exercise():
        bridge = BrainBridge(
            _enabled_settings(), transport=_mock_transport(handler)
        )
        return await bridge.call(
            "GET", "/brain/v1/capabilities", capability="capabilities"
        )

    response = asyncio.run(exercise())
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "BRAIN_UNAVAILABLE"
    assert response.error.details["reason"] == "MALFORMED_JSON"


def test_bridge_sends_envelope_body_on_post_and_includes_idempotency():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["body"] = json.loads(request.content or b"{}")
        captured["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            json={
                "ok": True,
                "contractVersion": "brain.internal.v1",
                "requestId": "brain-req-3",
                "correlationId": "brain-corr-3",
                "status": "READY",
                "executionAuthority": "NONE",
                "data": {"echo": True},
                "provenance": {"tenantId": "t2"},
            },
        )

    async def exercise():
        bridge = BrainBridge(
            _enabled_settings(), transport=_mock_transport(handler)
        )
        return await bridge.call(
            "POST",
            "/brain/v1/context",
            capability="context",
            payload={"goals": []},
            tenant_id="t2",
            workspace_id="w2",
            user_id="u2",
            role="manager",
            idempotency_key="idem-1",
        )

    response = asyncio.run(exercise())
    assert response.ok is True
    body = captured["body"]
    assert body["contractVersion"] == "brain.internal.v1"
    assert body["serviceIdentity"]["service"] == "executive-os"
    assert body["tenantContext"] == {"tenantId": "t2", "workspaceId": "w2"}
    assert body["userContext"] == {"userId": "u2", "role": "manager"}
    assert body["input"] == {"goals": []}
    assert body["idempotencyKey"] == "idem-1"
    assert captured["headers"]["idempotency-key"] == "idem-1"


def test_bridge_status_never_leaks_credentials():
    settings = _enabled_settings()
    bridge = BrainBridge(settings)
    status = bridge.status()
    assert status == {
        "enabled": True,
        "configured": True,
        "contract_version": "brain.internal.v1",
        "timeout_seconds": 2.0,
        "execution_authority": "NONE",
    }
    serialized = json.dumps(status)
    assert "bridge-test-secret" not in serialized
    assert "executive-os-test" not in serialized
