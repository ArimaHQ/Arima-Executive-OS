import asyncio
from collections.abc import Iterator

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.database.models import AuditEntity, AuditLog, LayaFailureClass, LayaTaskStatus
from app.laya.service import recovery_for
from tests.auth.conftest import AuthTestContext
from tests.auth.helpers import (
    bearer,
    csrf_headers,
    grant_role,
    login_user,
    register_user,
)
from tests.management.conftest import management_context

__all__ = ["management_context"]
BASE = "/api/v1/admin/founder/laya"


@pytest.fixture
def founder(management_context: AuthTestContext, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, str]]:
    monkeypatch.setenv("FOUNDER_CONTROL_EMAILS", "founder@example.com")
    get_settings.cache_clear()
    try:
        register_user(management_context, "founder@example.com")
        grant_role(management_context, "founder@example.com", "administrator")
        yield bearer(login_user(management_context, "founder@example.com")["access_token"])
    finally:
        get_settings.cache_clear()


def _post(context: AuthTestContext, headers: dict[str, str], path: str, payload: dict) -> object:
    return context.client.post(f"{BASE}{path}", json=payload, headers={**headers, **csrf_headers(context)})


def _task(context, headers, key: str, *, depends_on: tuple[str, ...] = (), criteria: bool = True) -> dict:
    response = _post(
        context, headers, "/tasks",
        {
            "key": key,
            "title": f"Task {key}",
            "purpose": "Verify orchestration invariants",
            "owner": "claude-code",
            "depends_on": list(depends_on),
            "acceptance_criteria": ["tests pass"] if criteria else [],
            "tests": ["tests/laya/test_laya.py"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _move(context, headers, key: str, *statuses: str) -> object:
    response = None
    for target in statuses:
        response = _post(context, headers, f"/tasks/{key}/transition", {"status": target})
        if response.status_code != 200:
            return response
    return response


def _evidence(context, headers, key: str, kind: str) -> None:
    response = _post(context, headers, f"/tasks/{key}/evidence", {"kind": kind, "reference": f"{kind}:{key}"})
    assert response.status_code == 200, response.text


def test_laya_is_founder_only(management_context: AuthTestContext, founder: dict[str, str]) -> None:
    context = management_context
    register_user(context, "client@example.com")
    client = bearer(login_user(context, "client@example.com")["access_token"])
    assert context.client.get(f"{BASE}/graph", headers=client).status_code == 403
    assert _post(context, client, "/tasks", {"key": "X", "title": "x", "purpose": "x", "owner": "x"}).status_code == 403
    assert context.client.get(f"{BASE}/graph").status_code == 401
    no_csrf = context.client.post(
        f"{BASE}/tasks",
        json={"key": "Y", "title": "y", "purpose": "y", "owner": "y"},
        headers=founder,
    )
    assert no_csrf.status_code == 403
    assert context.client.get(f"{BASE}/graph", headers=founder).json()["total"] == 0


def test_dependent_cannot_start_or_complete_before_its_dependency(management_context, founder) -> None:
    context = management_context
    _task(context, founder, "A")
    dependent = _task(context, founder, "B", depends_on=("A",))
    assert dependent["unmet_dependencies"] == ["A"]

    blocked = _move(context, founder, "B", "ready", "running")
    assert blocked.status_code == 409
    assert "depends on unfinished tasks: A" in blocked.json()["detail"]

    assert _move(context, founder, "A", "ready", "running", "verifying").status_code == 200
    no_tests = _move(context, founder, "A", "passed")
    assert no_tests.status_code == 409 and "test evidence" in no_tests.json()["detail"]
    _evidence(context, founder, "A", "test")
    assert _move(context, founder, "A", "passed").json()["status"] == "passed"
    no_e2e = _move(context, founder, "A", "completed")
    assert no_e2e.status_code == 409 and "e2e/production" in no_e2e.json()["detail"]
    _evidence(context, founder, "A", "e2e")
    assert _move(context, founder, "A", "completed").json()["status"] == "completed"

    started = _move(context, founder, "B", "running")
    assert started.status_code == 200 and started.json()["unmet_dependencies"] == []
    graph = context.client.get(f"{BASE}/graph", headers=founder).json()
    assert graph["counts"]["completed"] == 1 and graph["counts"]["running"] == 1


def test_completion_requires_acceptance_criteria(management_context, founder) -> None:
    context = management_context
    _task(context, founder, "NOCRIT", criteria=False)
    _move(context, founder, "NOCRIT", "ready", "running", "verifying")
    _evidence(context, founder, "NOCRIT", "test")
    _evidence(context, founder, "NOCRIT", "production_verification")
    _move(context, founder, "NOCRIT", "passed")
    response = _move(context, founder, "NOCRIT", "completed")
    assert response.status_code == 409 and "acceptance criteria" in response.json()["detail"]


def test_regressed_dependency_blocks_in_flight_dependents(management_context, founder) -> None:
    context = management_context
    _task(context, founder, "BASE")
    _task(context, founder, "TOP", depends_on=("BASE",))
    _move(context, founder, "BASE", "ready", "running", "verifying")
    _evidence(context, founder, "BASE", "test")
    _move(context, founder, "BASE", "passed")
    assert _move(context, founder, "TOP", "ready", "running").status_code == 200

    outcome = _post(
        context, founder, "/tasks/BASE/failures",
        {"failure_class": "code", "detail": "regression found in verification"},
    )
    assert outcome.status_code == 200
    assert outcome.json()["recovery_action"] == "repair_then_ready"
    assert outcome.json()["task"]["status"] == "failed"
    top = context.client.get(f"{BASE}/tasks/TOP", headers=founder).json()
    assert top["status"] == "blocked"
    assert "dependency BASE regressed" in top["blockers"]


def test_cycles_duplicates_and_unclassified_failures_are_rejected(management_context, founder) -> None:
    context = management_context
    _task(context, founder, "C1")
    _task(context, founder, "C2", depends_on=("C1",))
    cycle = _post(context, founder, "/tasks/C1/dependencies", {"depends_on": "C2"})
    assert cycle.status_code == 409 and "cycle" in cycle.json()["detail"]
    self_loop = _post(context, founder, "/tasks/C1/dependencies", {"depends_on": "C1"})
    assert self_loop.status_code == 409
    duplicate = _post(context, founder, "/tasks", {"key": "C1", "title": "dup", "purpose": "dup", "owner": "x"})
    assert duplicate.status_code == 409
    missing = _post(context, founder, "/tasks", {"key": "C3", "title": "x", "purpose": "x", "owner": "x", "depends_on": ["NOPE"]})
    assert missing.status_code == 404
    direct_fail = _move(context, founder, "C1", "ready", "running", "failed")
    assert direct_fail.status_code == 409 and "classification" in direct_fail.json()["detail"]
    blocked_without_reason = _move(context, founder, "C2", "blocked")
    assert blocked_without_reason.status_code == 409


def test_transient_failures_retry_then_escalate(management_context, founder) -> None:
    context = management_context
    response = _post(
        context, founder, "/tasks",
        {"key": "FLAKY", "title": "Fetch", "purpose": "Fetch source", "owner": "ingestion-agent", "max_attempts": 2},
    )
    assert response.status_code == 201
    _move(context, founder, "FLAKY", "ready", "running")
    first = _post(context, founder, "/tasks/FLAKY/failures", {"failure_class": "transient", "detail": "timeout"})
    assert first.json()["recovery_action"] == "retry"
    assert first.json()["task"]["status"] == "retry" and first.json()["task"]["attempts"] == 2
    _move(context, founder, "FLAKY", "running")
    second = _post(context, founder, "/tasks/FLAKY/failures", {"failure_class": "transient", "detail": "timeout"})
    assert second.json()["recovery_action"] == "retries_exhausted_escalate"
    task = second.json()["task"]
    assert task["status"] == "blocked" and task["requires_human"] is True
    graph = context.client.get(f"{BASE}/graph", headers=founder).json()
    assert graph["requires_human"] == ["FLAKY"] and graph["blocked"] == ["FLAKY"]


def test_every_failure_class_has_a_recovery_path() -> None:
    expected = {
        LayaFailureClass.TRANSIENT: (LayaTaskStatus.RETRY, False),
        LayaFailureClass.DATA: (LayaTaskStatus.FAILED, False),
        LayaFailureClass.CODE: (LayaTaskStatus.FAILED, False),
        LayaFailureClass.DEPENDENCY: (LayaTaskStatus.BLOCKED, False),
        LayaFailureClass.PERMISSION: (LayaTaskStatus.BLOCKED, True),
        LayaFailureClass.INFRASTRUCTURE: (LayaTaskStatus.BLOCKED, True),
        LayaFailureClass.ARCHITECTURAL: (LayaTaskStatus.BLOCKED, True),
    }
    for failure, (status, human) in expected.items():
        decision = recovery_for(failure, attempts=1, max_attempts=3)
        assert (decision.status, decision.requires_human) == (status, human), failure


def test_laya_mutations_are_audited(management_context, founder) -> None:
    context = management_context
    _task(context, founder, "AUD")
    _move(context, founder, "AUD", "ready")
    _evidence(context, founder, "AUD", "log")

    async def count() -> int:
        async with context.session_factory() as session:
            return int(
                await session.scalar(
                    select(func.count(AuditLog.id)).where(AuditLog.entity == AuditEntity.LAYA_TASK)
                )
            )

    assert asyncio.run(count()) == 3
