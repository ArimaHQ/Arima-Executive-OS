"""HTTP client for the private Node Brain (Arima-Brain-AUTHORITATIVE).

Executive OS is the CALLER, Brain is the CALLEE. This bridge does not
duplicate any Brain functionality; it forwards a canonical envelope and
returns the Brain's response verbatim (data + provenance) or a fail-closed
error.

Contract reference:
``ARIMA-PC-MIGRATION-WORK/ARIMA/Arima-Brain-AUTHORITATIVE/docs/BRAIN_INTERNAL_API_CONTRACT.md``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import httpx

from app.core.config import Settings
from app.schemas.brain import BrainErrorBody, BrainProxyResponse

logger = logging.getLogger("arima.brain_bridge")


class BrainBridgeError(Exception):
    """Raised for programming errors — never for upstream Brain failures."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fail_closed(
    code: str,
    message: str,
    *,
    request_id: str,
    correlation_id: str,
    contract_version: str,
    retryable: bool = False,
    details: Mapping[str, Any] | None = None,
) -> BrainProxyResponse:
    return BrainProxyResponse(
        ok=False,
        contract_version=contract_version,
        request_id=request_id,
        correlation_id=correlation_id,
        status="BRAIN_UNAVAILABLE" if code == "BRAIN_UNAVAILABLE" else None,
        error=BrainErrorBody(
            code=code,
            message=message,
            retryable=retryable,
            details=dict(details or {}),
        ),
    )


class BrainBridge:
    """Minimal fail-closed HTTP bridge to the private Node Brain.

    A single instance is safe to reuse for multiple requests; each ``get`` /
    ``post`` call opens its own ``httpx.AsyncClient`` so tests can inject a
    transport per call.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    def status(self) -> dict[str, Any]:
        settings = self._settings
        configured = bool(
            settings.brain_internal_url
            and settings.brain_internal_credential_id
            and settings.brain_internal_credential_secret
        )
        return {
            "enabled": bool(settings.brain_internal_enabled),
            "configured": configured,
            "contract_version": settings.brain_internal_contract_version,
            "timeout_seconds": settings.brain_internal_timeout_seconds,
            "execution_authority": "NONE",
        }

    def _envelope(
        self,
        *,
        capability: str,
        payload: Mapping[str, Any] | None,
        tenant_id: str | None,
        workspace_id: str | None,
        user_id: str | None,
        role: str | None,
        request_id: str,
        correlation_id: str,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        settings = self._settings
        envelope: dict[str, Any] = {
            "requestId": request_id,
            "correlationId": correlation_id,
            "contractVersion": settings.brain_internal_contract_version,
            "serviceIdentity": {
                "service": "executive-os",
                "credentialId": settings.brain_internal_credential_id or "",
            },
            "tenantContext": {
                "tenantId": tenant_id or "",
                "workspaceId": workspace_id or "",
            },
            "userContext": {
                "userId": user_id or "",
                "role": role or "",
            },
            "requestedAt": _now_iso(),
            "capability": capability,
            "input": dict(payload or {}),
        }
        if idempotency_key:
            envelope["idempotencyKey"] = idempotency_key
        return envelope

    async def call(
        self,
        method: str,
        path: str,
        *,
        capability: str,
        payload: Mapping[str, Any] | None = None,
        tenant_id: str | None = None,
        workspace_id: str | None = None,
        user_id: str | None = None,
        role: str | None = None,
        correlation_id: UUID | str | None = None,
        idempotency_key: str | None = None,
    ) -> BrainProxyResponse:
        """Send a request to the Node Brain and return the mapped envelope.

        Every failure mode (disabled, unconfigured, network error, non-2xx,
        malformed JSON) returns a ``BrainProxyResponse(ok=False)`` — never
        raises to the caller.
        """
        settings = self._settings
        contract_version = settings.brain_internal_contract_version
        request_id = str(uuid4())
        correlation_id_str = (
            str(correlation_id) if correlation_id is not None else request_id
        )

        if not settings.brain_internal_enabled:
            return _fail_closed(
                "BRAIN_UNAVAILABLE",
                "Brain bridge is disabled",
                request_id=request_id,
                correlation_id=correlation_id_str,
                contract_version=contract_version,
                retryable=False,
                details={"reason": "BRAIN_INTERNAL_ENABLED=false"},
            )

        if not (
            settings.brain_internal_url
            and settings.brain_internal_credential_id
            and settings.brain_internal_credential_secret
        ):
            return _fail_closed(
                "BRAIN_UNAVAILABLE",
                "Brain bridge is not fully configured",
                request_id=request_id,
                correlation_id=correlation_id_str,
                contract_version=contract_version,
                retryable=False,
                details={"reason": "MISSING_CREDENTIAL_OR_URL"},
            )

        envelope = self._envelope(
            capability=capability,
            payload=payload,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
            request_id=request_id,
            correlation_id=correlation_id_str,
            idempotency_key=idempotency_key,
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": (
                "Bearer "
                + settings.brain_internal_credential_secret.get_secret_value()
            ),
            "X-Correlation-ID": correlation_id_str,
            "X-Request-ID": request_id,
            "X-Contract-Version": contract_version,
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        base_url = settings.brain_internal_url.rstrip("/")
        url = base_url + (path if path.startswith("/") else f"/{path}")

        try:
            async with httpx.AsyncClient(
                timeout=settings.brain_internal_timeout_seconds,
                transport=self._transport,
            ) as client:
                request_kwargs: dict[str, Any] = {"headers": headers}
                if method.upper() in {"POST", "PUT", "PATCH"}:
                    request_kwargs["json"] = envelope
                else:
                    # Read-only calls forward the envelope as query metadata is
                    # not part of contract v1; we send the envelope on the
                    # request line only for methods that carry a body.
                    request_kwargs["headers"] = {
                        **headers,
                        "X-Brain-Envelope": "omitted-on-read",
                    }
                response = await client.request(
                    method.upper(), url, **request_kwargs
                )
        except httpx.TimeoutException as error:
            logger.warning(
                "brain_bridge_timeout",
                extra={
                    "correlation_id": correlation_id_str,
                    "capability": capability,
                },
            )
            return _fail_closed(
                "BRAIN_UNAVAILABLE",
                "Brain request timed out",
                request_id=request_id,
                correlation_id=correlation_id_str,
                contract_version=contract_version,
                retryable=True,
                details={"reason": "TIMEOUT", "error": type(error).__name__},
            )
        except httpx.HTTPError as error:
            logger.warning(
                "brain_bridge_transport_error",
                extra={
                    "correlation_id": correlation_id_str,
                    "capability": capability,
                    "error": type(error).__name__,
                },
            )
            return _fail_closed(
                "BRAIN_UNAVAILABLE",
                "Brain request failed to complete",
                request_id=request_id,
                correlation_id=correlation_id_str,
                contract_version=contract_version,
                retryable=True,
                details={"reason": "TRANSPORT_ERROR"},
            )

        if response.status_code >= 500:
            return _fail_closed(
                "BRAIN_UNAVAILABLE",
                "Brain returned an error",
                request_id=request_id,
                correlation_id=correlation_id_str,
                contract_version=contract_version,
                retryable=True,
                details={"reason": "UPSTREAM_5XX", "status": response.status_code},
            )

        try:
            body = response.json()
        except ValueError:
            return _fail_closed(
                "BRAIN_UNAVAILABLE",
                "Brain returned an unreadable response",
                request_id=request_id,
                correlation_id=correlation_id_str,
                contract_version=contract_version,
                retryable=False,
                details={"reason": "MALFORMED_JSON", "status": response.status_code},
            )

        # Node Brain successful envelope contains ok=true. Non-success is a
        # deterministic error envelope from the callee.
        if isinstance(body, dict) and body.get("ok") is False:
            error = body.get("error") or {}
            return BrainProxyResponse(
                ok=False,
                contract_version=contract_version,
                request_id=body.get("requestId", request_id),
                correlation_id=body.get("correlationId", correlation_id_str),
                error=BrainErrorBody(
                    code=str(error.get("code", "BRAIN_ERROR")),
                    message=str(
                        error.get("message", "Brain returned an error")
                    ),
                    retryable=bool(error.get("retryable", False)),
                    details=dict(error.get("details") or {}),
                ),
            )

        # Success path — the Node Brain returns {data: ..., provenance: ...}.
        if isinstance(body, dict):
            data = body.get("data")
            provenance = body.get("provenance")
        else:
            data = None
            provenance = None

        return BrainProxyResponse(
            ok=True,
            contract_version=contract_version,
            request_id=request_id,
            correlation_id=correlation_id_str,
            status=str(body.get("status")) if isinstance(body, dict) and body.get("status") else None,
            data=data if isinstance(data, dict) else ({"value": data} if data is not None else None),
            provenance=provenance if isinstance(provenance, dict) else None,
        )
