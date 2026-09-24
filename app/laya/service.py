"""Laya: dependency-aware work orchestration with evidence gates.

Invariants enforced here (and tested):
- a task cannot start, verify, pass or complete while any dependency is below
  PASSED;
- PASSED requires test evidence; COMPLETED additionally requires end-to-end or
  production verification evidence and acceptance criteria;
- every failure is classified and mapped to retry, repair, or escalation;
- a dependency that regresses blocks its in-flight dependents;
- dependencies cannot form a cycle, and task keys are unique.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    AuditAction,
    AuditEntity,
    LayaFailureClass,
    LayaTask,
    LayaTaskDependency,
    LayaTaskStatus,
    User,
)
from app.laya.schemas import (
    LayaEvidenceCreate,
    LayaFailureReport,
    LayaGraphSummary,
    LayaTaskCreate,
    LayaTaskRead,
)
from app.services.audit import record_audit

S = LayaTaskStatus

TRANSITIONS: dict[LayaTaskStatus, frozenset[LayaTaskStatus]] = {
    S.DISCOVERED: frozenset({S.READY, S.BLOCKED, S.REJECTED}),
    S.READY: frozenset({S.RUNNING, S.BLOCKED, S.REJECTED}),
    S.RUNNING: frozenset({S.VERIFYING, S.FAILED, S.BLOCKED}),
    S.VERIFYING: frozenset({S.PASSED, S.FAILED}),
    S.PASSED: frozenset({S.COMPLETED, S.FAILED}),
    S.FAILED: frozenset({S.RETRY, S.READY, S.BLOCKED, S.REJECTED}),
    S.RETRY: frozenset({S.RUNNING, S.BLOCKED}),
    S.BLOCKED: frozenset({S.READY, S.REJECTED}),
    S.COMPLETED: frozenset(),
    S.REJECTED: frozenset(),
}
SATISFIED = frozenset({S.PASSED, S.COMPLETED})
REQUIRES_SATISFIED_DEPENDENCIES = frozenset({S.RUNNING, S.VERIFYING, S.PASSED, S.COMPLETED})
IN_FLIGHT = frozenset({S.RUNNING, S.VERIFYING, S.PASSED, S.RETRY})
STALE_CANDIDATES = frozenset({S.RUNNING, S.VERIFYING, S.RETRY})
VERIFICATION_EVIDENCE = frozenset({"e2e", "production_verification"})


class LayaError(RuntimeError):
    pass


class LayaNotFoundError(LayaError):
    pass


class LayaConflictError(LayaError):
    pass


class LayaTransitionError(LayaError):
    pass


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    status: LayaTaskStatus
    action: str
    requires_human: bool


def recovery_for(failure: LayaFailureClass, *, attempts: int, max_attempts: int) -> RecoveryDecision:
    """Map a classified failure to its recovery path."""
    if failure is LayaFailureClass.TRANSIENT:
        if attempts < max_attempts:
            return RecoveryDecision(S.RETRY, "retry", False)
        return RecoveryDecision(S.BLOCKED, "retries_exhausted_escalate", True)
    if failure in (LayaFailureClass.DATA, LayaFailureClass.CODE):
        return RecoveryDecision(S.FAILED, "repair_then_ready", False)
    if failure is LayaFailureClass.DEPENDENCY:
        return RecoveryDecision(S.BLOCKED, "resolve_dependency", False)
    if failure is LayaFailureClass.ARCHITECTURAL:
        return RecoveryDecision(S.BLOCKED, "stop_patching_reassess_architecture", True)
    return RecoveryDecision(S.BLOCKED, "escalate_with_recovery_path", True)


class LayaService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: LayaTaskCreate, *, actor: User) -> LayaTaskRead:
        if await self._by_key(data.key) is not None:
            raise LayaConflictError(f"Task {data.key} already exists")
        dependencies = [await self._require(key) for key in data.depends_on]
        task = LayaTask(
            key=data.key,
            title=data.title,
            purpose=data.purpose,
            owner=data.owner,
            status=S.DISCOVERED,
            inputs=list(data.inputs),
            outputs=list(data.outputs),
            systems=list(data.systems),
            acceptance_criteria=list(data.acceptance_criteria),
            tests=list(data.tests),
            evidence=[],
            blockers=[],
            attempts=0,
            max_attempts=data.max_attempts,
            requires_human=False,
            created_by_id=actor.id,
        )
        self.session.add(task)
        await self.session.flush()
        self.session.add_all(
            LayaTaskDependency(task_id=task.id, depends_on_id=dependency.id)
            for dependency in dependencies
        )
        self._audit(actor, task, AuditAction.CREATE)
        await self.session.commit()
        return await self.read(task.key)

    async def add_dependency(self, key: str, depends_on: str, *, actor: User) -> LayaTaskRead:
        task = await self._require(key)
        dependency = await self._require(depends_on)
        if task.id == dependency.id:
            raise LayaConflictError("A task cannot depend on itself")
        if task.status in (S.COMPLETED, S.REJECTED):
            raise LayaTransitionError("Terminal tasks cannot gain dependencies")
        if await self._reaches(dependency.id, task.id):
            raise LayaConflictError("Dependency would create a cycle")
        existing = await self.session.get(LayaTaskDependency, (task.id, dependency.id))
        if existing is None:
            self.session.add(LayaTaskDependency(task_id=task.id, depends_on_id=dependency.id))
            if task.status in IN_FLIGHT and dependency.status not in SATISFIED:
                self._block(task, f"new dependency {dependency.key} is {dependency.status.value}")
            self._audit(actor, task, AuditAction.UPDATE)
            await self.session.commit()
        return await self.read(key)

    async def add_evidence(self, key: str, data: LayaEvidenceCreate, *, actor: User) -> LayaTaskRead:
        task = await self._require(key)
        task.evidence = [
            *task.evidence,
            {
                "kind": data.kind,
                "reference": data.reference,
                "recorded_at": datetime.now(UTC).isoformat(),
                "recorded_by": str(actor.id),
            },
        ]
        self._audit(actor, task, AuditAction.UPDATE)
        await self.session.commit()
        return await self.read(key)

    async def transition(
        self,
        key: str,
        target: LayaTaskStatus,
        *,
        actor: User,
        blocker: str | None = None,
    ) -> LayaTaskRead:
        task = await self._require(key)
        if target is S.FAILED:
            raise LayaTransitionError("Report failures through record_failure with a classification")
        if target not in TRANSITIONS[task.status]:
            raise LayaTransitionError(
                f"{task.key}: {task.status.value} -> {target.value} is not allowed"
            )
        if target in REQUIRES_SATISFIED_DEPENDENCIES:
            unmet = await self._unmet_dependencies(task)
            if unmet:
                raise LayaTransitionError(
                    f"{task.key} depends on unfinished tasks: {', '.join(sorted(unmet))}"
                )
        kinds = {item.get("kind") for item in task.evidence}
        if target is S.PASSED and "test" not in kinds:
            raise LayaTransitionError(f"{task.key} needs test evidence before PASSED")
        if target is S.COMPLETED:
            if not task.acceptance_criteria:
                raise LayaTransitionError(f"{task.key} has no acceptance criteria")
            if "test" not in kinds or not kinds.intersection(VERIFICATION_EVIDENCE):
                raise LayaTransitionError(
                    f"{task.key} needs test and e2e/production verification evidence before COMPLETED"
                )
        if target is S.BLOCKED:
            if not blocker:
                raise LayaTransitionError("A blocker description is required")
            self._block(task, blocker)
        else:
            task.status = target
        if target in (S.READY, S.RUNNING):
            task.blockers = []
            task.requires_human = False
            if target is S.READY:
                task.failure_class = None
        if target is S.RUNNING and task.attempts == 0:
            task.attempts = 1
        self._audit(actor, task, AuditAction.STATUS_CHANGE)
        await self.session.commit()
        return await self.read(key)

    async def record_failure(self, key: str, report: LayaFailureReport, *, actor: User) -> tuple[LayaTaskRead, str]:
        task = await self._require(key)
        if task.status not in (S.RUNNING, S.VERIFYING, S.PASSED, S.RETRY):
            raise LayaTransitionError(f"{task.key} is not in progress ({task.status.value})")
        regressed = task.status is S.PASSED
        task.failure_class = report.failure_class
        decision = recovery_for(
            report.failure_class, attempts=task.attempts, max_attempts=task.max_attempts
        )
        if decision.status is S.RETRY:
            task.attempts += 1
        task.blockers = [*task.blockers, f"{report.failure_class.value}: {report.detail}"]
        task.status = decision.status
        task.requires_human = decision.requires_human
        if regressed:
            for dependent in await self._dependents(task.id):
                if dependent.status in IN_FLIGHT:
                    self._block(dependent, f"dependency {task.key} regressed")
                    self._audit(actor, dependent, AuditAction.STATUS_CHANGE)
        self._audit(actor, task, AuditAction.STATUS_CHANGE)
        await self.session.commit()
        return await self.read(key), decision.action

    async def read(self, key: str) -> LayaTaskRead:
        task = await self._require(key)
        dependencies = await self._dependencies(task.id)
        return LayaTaskRead(
            id=task.id,
            key=task.key,
            title=task.title,
            purpose=task.purpose,
            owner=task.owner,
            status=task.status,
            depends_on=sorted(item.key for item in dependencies),
            unmet_dependencies=sorted(
                item.key for item in dependencies if item.status not in SATISFIED
            ),
            inputs=task.inputs,
            outputs=task.outputs,
            systems=task.systems,
            acceptance_criteria=task.acceptance_criteria,
            tests=task.tests,
            evidence=task.evidence,
            blockers=task.blockers,
            failure_class=task.failure_class,
            attempts=task.attempts,
            max_attempts=task.max_attempts,
            requires_human=task.requires_human,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    async def list(self, status: LayaTaskStatus | None = None) -> list[LayaTaskRead]:
        query = select(LayaTask.key).order_by(LayaTask.key)
        if status is not None:
            query = query.where(LayaTask.status == status)
        return [await self.read(key) for key in (await self.session.scalars(query)).all()]

    async def summary(self, *, now: datetime | None = None, stale_after: timedelta = timedelta(hours=24)) -> LayaGraphSummary:
        tasks = (await self.session.scalars(select(LayaTask))).all()
        counts = {status.value: 0 for status in LayaTaskStatus}
        for task in tasks:
            counts[task.status.value] += 1
        checked_at = now or datetime.now(UTC)
        ready: list[str] = []
        for task in tasks:
            if task.status is S.READY and not await self._unmet_dependencies(task):
                ready.append(task.key)
        stale = [
            task.key
            for task in tasks
            if task.status in STALE_CANDIDATES
            and _aware(task.updated_at) < checked_at - stale_after
        ]
        return LayaGraphSummary(
            total=len(tasks),
            counts=counts,
            ready_to_start=sorted(ready),
            blocked=sorted(task.key for task in tasks if task.status is S.BLOCKED),
            requires_human=sorted(task.key for task in tasks if task.requires_human),
            stale=sorted(stale),
        )

    async def _by_key(self, key: str) -> LayaTask | None:
        return await self.session.scalar(select(LayaTask).where(LayaTask.key == key))

    async def _require(self, key: str) -> LayaTask:
        task = await self._by_key(key)
        if task is None:
            raise LayaNotFoundError(f"Task {key} was not found")
        return task

    async def _dependencies(self, task_id: UUID) -> list[LayaTask]:
        return list(
            (
                await self.session.scalars(
                    select(LayaTask)
                    .join(LayaTaskDependency, LayaTaskDependency.depends_on_id == LayaTask.id)
                    .where(LayaTaskDependency.task_id == task_id)
                )
            ).all()
        )

    async def _dependents(self, task_id: UUID) -> list[LayaTask]:
        return list(
            (
                await self.session.scalars(
                    select(LayaTask)
                    .join(LayaTaskDependency, LayaTaskDependency.task_id == LayaTask.id)
                    .where(LayaTaskDependency.depends_on_id == task_id)
                )
            ).all()
        )

    async def _unmet_dependencies(self, task: LayaTask) -> set[str]:
        return {
            item.key for item in await self._dependencies(task.id) if item.status not in SATISFIED
        }

    async def _reaches(self, start: UUID, target: UUID) -> bool:
        """True when ``target`` is reachable from ``start`` along dependencies."""
        pending: list[UUID] = [start]
        seen: set[UUID] = set()
        while pending:
            current = pending.pop()
            if current == target:
                return True
            if current in seen:
                continue
            seen.add(current)
            pending.extend(item.id for item in await self._dependencies(current))
        return False

    @staticmethod
    def _block(task: LayaTask, blocker: str) -> None:
        task.status = S.BLOCKED
        task.blockers = [*task.blockers, blocker]

    def _audit(self, actor: User, task: LayaTask, action: AuditAction) -> None:
        record_audit(
            self.session,
            actor_id=actor.id,
            action=action,
            entity=AuditEntity.LAYA_TASK,
            entity_id=task.id,
        )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
