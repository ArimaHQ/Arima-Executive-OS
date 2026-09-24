"""Schemas for the private Node Brain bridge.

These mirror the ``brain.internal.v1`` envelope documented in
``docs/BRAIN_INTERNAL_API_CONTRACT.md`` on the Node Brain side. The Executive OS
never fabricates Brain data; every non-success outcome is a deterministic,
fail-closed structured error the caller can render.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class BrainBridgeStatus(BaseModel):
    """Non-sensitive bridge health for public status routes.

    The credential values are never included; only whether the operator
    supplied them.
    """

    enabled: bool
    configured: bool = Field(
        description="True when a URL and credential id/secret are supplied."
    )
    contract_version: str
    timeout_seconds: float
    execution_authority: Literal["NONE"] = "NONE"


class BrainErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class BrainProxyResponse(BaseModel):
    """Envelope surfaced to Executive OS callers.

    ``ok=True`` mirrors the Node Brain success envelope; ``ok=False`` maps every
    upstream error (unreachable, timeout, non-2xx, malformed) to an explicit
    ``BRAIN_UNAVAILABLE`` or upstream ``error.code`` without leaking topology.
    """

    ok: bool
    contract_version: str
    request_id: str
    correlation_id: str
    execution_authority: Literal["NONE"] = "NONE"
    status: str | None = None
    data: dict[str, Any] | None = None
    provenance: dict[str, Any] | None = None
    error: BrainErrorBody | None = None
