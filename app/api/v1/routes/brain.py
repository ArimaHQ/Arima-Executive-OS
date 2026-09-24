"""Executive OS → private Node Brain bridge routes.

This module owns the customer-side of the bridge only. All financial logic,
evidence, and reasoning remain in the Node Brain (Arima-Brain-AUTHORITATIVE).
Python never fabricates a Brain answer: when the bridge is disabled, unreachable,
or returns an error the response is a deterministic ``BRAIN_UNAVAILABLE`` /
Brain-supplied error envelope.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_active_user
from app.core.config import Settings, get_settings
from app.database.models import User
from app.schemas.brain import BrainBridgeStatus, BrainProxyResponse
from app.services.brain_bridge import BrainBridge

router = APIRouter(prefix="/brain", tags=["brain"])
SettingsDependency = Annotated[Settings, Depends(get_settings)]
AuthedUser = Annotated[User, Depends(get_current_active_user)]


def _bridge(settings: Settings) -> BrainBridge:
    return BrainBridge(settings)


@router.get("/status", response_model=BrainBridgeStatus)
async def brain_status(settings: SettingsDependency) -> BrainBridgeStatus:
    """Non-sensitive bridge health. Never returns credentials."""
    return BrainBridgeStatus(**_bridge(settings).status())


@router.get("/capabilities", response_model=BrainProxyResponse)
async def brain_capabilities(
    settings: SettingsDependency,
    user: AuthedUser,
) -> BrainProxyResponse:
    """Proxy ``GET /brain/v1/capabilities`` on the private Node Brain."""
    return await _bridge(settings).call(
        "GET",
        "/brain/v1/capabilities",
        capability="capabilities",
        user_id=str(user.id),
    )


@router.get("/context", response_model=BrainProxyResponse)
async def brain_context(
    settings: SettingsDependency,
    user: AuthedUser,
) -> BrainProxyResponse:
    """Proxy ``GET /brain/v1/context`` on the private Node Brain."""
    return await _bridge(settings).call(
        "GET",
        "/brain/v1/context",
        capability="context",
        user_id=str(user.id),
    )
