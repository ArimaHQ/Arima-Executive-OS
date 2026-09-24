from dataclasses import FrozenInstanceError
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.execution_policy import (
    EXECUTION_POLICY,
    ExecutionAuthority,
    ExecutionNotAuthorizedError,
    ExecutionPolicy,
    ExternalExecution,
)
from app.services.trading_contracts import DisabledQTradeExecution


def test_policy_is_the_security_authorized_posture() -> None:
    assert EXECUTION_POLICY.as_dict() == {
        "execution_authority": "NONE",
        "live_execution": False,
        "autonomous_execution": False,
        "paper_execution": True,
        "external_execution": "DISCONNECTED",
    }


def test_policy_is_immutable_at_runtime() -> None:
    with pytest.raises(FrozenInstanceError):
        EXECUTION_POLICY.live_execution = True  # type: ignore[misc]


@pytest.mark.parametrize(
    "overrides",
    [
        {"live_execution": True},
        {"autonomous_execution": True},
        {"paper_execution": False},
    ],
)
def test_no_other_posture_can_be_constructed(overrides: dict[str, bool]) -> None:
    values = {
        "execution_authority": ExecutionAuthority.NONE,
        "live_execution": False,
        "autonomous_execution": False,
        "paper_execution": True,
        "external_execution": ExternalExecution.DISCONNECTED,
        **overrides,
    }
    with pytest.raises(ExecutionNotAuthorizedError):
        ExecutionPolicy(**values)


def test_live_and_autonomous_execution_fail_closed() -> None:
    with pytest.raises(ExecutionNotAuthorizedError, match="not enabled"):
        EXECUTION_POLICY.require_live_execution(action="Broker order")
    with pytest.raises(ExecutionNotAuthorizedError, match="human authorization"):
        EXECUTION_POLICY.require_autonomous_execution(action="Rebalance")


@pytest.mark.asyncio
async def test_disabled_qtrade_submission_is_blocked_by_the_policy() -> None:
    with pytest.raises(ExecutionNotAuthorizedError, match="QTRADE order submission is not enabled"):
        await DisabledQTradeExecution().submit_order(
            workspace_id=uuid4(), account_id=uuid4(), asset="XAUUSD", quantity=Decimal(1)
        )


def test_no_setting_can_enable_execution() -> None:
    from app.core.config import Settings

    exposed = {name.lower() for name in Settings.model_fields}
    for forbidden in ("live_execution", "execution_authority", "autonomous_execution", "external_execution"):
        assert not any(forbidden in name for name in exposed), forbidden
