"""Laya orchestration task graph.

Laya coordinates work; it never reasons about markets or users (that is the
Brain). A task records who owns it, what it depends on, how it is accepted,
and the evidence that proves it. Status transitions are enforced by
``app.laya.service``.
"""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.models.intelligence import intelligence_enum


class LayaTaskStatus(str, Enum):
    DISCOVERED = "discovered"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    FAILED = "failed"
    RETRY = "retry"
    VERIFYING = "verifying"
    PASSED = "passed"
    COMPLETED = "completed"
    REJECTED = "rejected"


class LayaFailureClass(str, Enum):
    TRANSIENT = "transient"
    DATA = "data"
    CODE = "code"
    DEPENDENCY = "dependency"
    PERMISSION = "permission"
    INFRASTRUCTURE = "infrastructure"
    ARCHITECTURAL = "architectural"


class LayaTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "laya_tasks"

    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[LayaTaskStatus] = mapped_column(
        intelligence_enum(LayaTaskStatus, "laya_task_status"),
        default=LayaTaskStatus.DISCOVERED,
        nullable=False,
    )
    inputs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    outputs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    systems: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    acceptance_criteria: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    tests: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence: Mapped[list[dict[str, str]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    blockers: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    failure_class: Mapped[LayaFailureClass | None] = mapped_column(
        intelligence_enum(LayaFailureClass, "laya_failure_class"),
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    requires_human: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_by_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("attempts >= 0", name="laya_task_attempts_non_negative"),
        CheckConstraint("max_attempts >= 1", name="laya_task_max_attempts_positive"),
        Index("ix_laya_tasks_status_updated", "status", "updated_at"),
    )


class LayaTaskDependency(Base):
    __tablename__ = "laya_task_dependencies"

    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("laya_tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    depends_on_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("laya_tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )

    __table_args__ = (
        CheckConstraint("task_id <> depends_on_id", name="laya_task_dependency_not_self"),
        Index("ix_laya_task_dependencies_depends_on", "depends_on_id"),
    )
