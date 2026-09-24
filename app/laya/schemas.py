from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.database.models.laya import LayaFailureClass, LayaTaskStatus

TaskKey = str

EvidenceKind = Literal[
    "test", "e2e", "production_verification", "log", "document", "commit"
]


class LayaSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _clean(items: list[str]) -> list[str]:
    cleaned = [item.strip() for item in items]
    if any(not item for item in cleaned):
        raise ValueError("List entries cannot be blank")
    return cleaned


class LayaTaskCreate(LayaSchema):
    key: TaskKey = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    title: str = Field(min_length=1, max_length=300)
    purpose: str = Field(min_length=1, max_length=5_000)
    owner: str = Field(min_length=1, max_length=120)
    depends_on: list[TaskKey] = Field(default_factory=list, max_length=50)
    inputs: list[str] = Field(default_factory=list, max_length=50)
    outputs: list[str] = Field(default_factory=list, max_length=50)
    systems: list[str] = Field(default_factory=list, max_length=100)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=50)
    tests: list[str] = Field(default_factory=list, max_length=100)
    max_attempts: int = Field(default=3, ge=1, le=10)

    _clean_lists = field_validator(
        "depends_on", "inputs", "outputs", "systems", "acceptance_criteria", "tests"
    )(_clean)


class LayaDependencyCreate(LayaSchema):
    depends_on: TaskKey = Field(min_length=1, max_length=64)


class LayaTransitionRequest(LayaSchema):
    status: LayaTaskStatus
    blocker: str | None = Field(default=None, min_length=1, max_length=2_000)


class LayaEvidenceCreate(LayaSchema):
    kind: EvidenceKind
    reference: str = Field(min_length=1, max_length=2_000)


class LayaFailureReport(LayaSchema):
    failure_class: LayaFailureClass
    detail: str = Field(min_length=1, max_length=2_000)


class LayaTaskRead(LayaSchema):
    id: UUID
    key: str
    title: str
    purpose: str
    owner: str
    status: LayaTaskStatus
    depends_on: list[str]
    unmet_dependencies: list[str]
    inputs: list[str]
    outputs: list[str]
    systems: list[str]
    acceptance_criteria: list[str]
    tests: list[str]
    evidence: list[dict[str, str]]
    blockers: list[str]
    failure_class: LayaFailureClass | None
    attempts: int
    max_attempts: int
    requires_human: bool
    created_at: datetime
    updated_at: datetime


class LayaFailureOutcome(LayaSchema):
    task: LayaTaskRead
    recovery_action: str


class LayaGraphSummary(LayaSchema):
    total: int
    counts: dict[str, int]
    ready_to_start: list[str]
    blocked: list[str]
    requires_human: list[str]
    stale: list[str]
