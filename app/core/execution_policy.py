"""Single authoritative financial-execution policy.

Every path that could move capital or submit an order consults this module.
The policy is deliberately not configurable: there is no environment
variable, setting, or API that can widen it. Changing it requires a reviewed
code change to ``_LOCKED_POSTURE`` together with an explicit security
authorization, which is the control the architecture requires.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum


class ExecutionAuthority(StrEnum):
    NONE = "NONE"


class ExternalExecution(StrEnum):
    DISCONNECTED = "DISCONNECTED"


class ExecutionNotAuthorizedError(RuntimeError):
    """Raised when any code path attempts live or autonomous execution."""


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    execution_authority: ExecutionAuthority
    live_execution: bool
    autonomous_execution: bool
    paper_execution: bool
    external_execution: ExternalExecution

    def __post_init__(self) -> None:
        if self.as_dict() != _LOCKED_POSTURE:
            raise ExecutionNotAuthorizedError(
                "Execution policy differs from the security-authorized posture"
            )

    def as_dict(self) -> dict[str, object]:
        values = asdict(self)
        return {
            key: value.value if isinstance(value, StrEnum) else value
            for key, value in values.items()
        }

    def require_live_execution(self, *, action: str) -> None:
        """Fail closed for any live, broker, or capital-moving action."""
        if (
            self.execution_authority is ExecutionAuthority.NONE
            or not self.live_execution
            or self.external_execution is ExternalExecution.DISCONNECTED
        ):
            raise ExecutionNotAuthorizedError(
                f"{action} is not enabled: execution authority is "
                f"{self.execution_authority.value}"
            )

    def require_autonomous_execution(self, *, action: str) -> None:
        if not self.autonomous_execution:
            raise ExecutionNotAuthorizedError(
                f"{action} requires human authorization: autonomous execution is disabled"
            )


_LOCKED_POSTURE: dict[str, object] = {
    "execution_authority": "NONE",
    "live_execution": False,
    "autonomous_execution": False,
    "paper_execution": True,
    "external_execution": "DISCONNECTED",
}

EXECUTION_POLICY = ExecutionPolicy(
    execution_authority=ExecutionAuthority.NONE,
    live_execution=False,
    autonomous_execution=False,
    paper_execution=True,
    external_execution=ExternalExecution.DISCONNECTED,
)
