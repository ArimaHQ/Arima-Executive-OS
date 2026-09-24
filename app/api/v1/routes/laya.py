"""Founder-only Laya API: Jarvis -> Laya -> task graph.

Only Founder Control (allowlisted, verified administrator, MFA in production)
can read or change the graph. Every mutation is CSRF-protected and audited.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.csrf import require_valid_csrf
from app.auth.dependencies import require_founder_control
from app.database.models import LayaTaskStatus, User
from app.database.session import get_session
from app.laya.schemas import (
    LayaDependencyCreate,
    LayaEvidenceCreate,
    LayaFailureOutcome,
    LayaFailureReport,
    LayaGraphSummary,
    LayaTaskCreate,
    LayaTaskRead,
    LayaTransitionRequest,
)
from app.laya.service import (
    LayaConflictError,
    LayaError,
    LayaNotFoundError,
    LayaService,
    LayaTransitionError,
)

router = APIRouter(prefix="/admin/founder/laya", tags=["laya"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
FounderUser = Annotated[User, Depends(require_founder_control)]


def _csrf(request: Request) -> None:
    require_valid_csrf(request)


def _error(error: LayaError) -> HTTPException:
    if isinstance(error, LayaNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, (LayaConflictError, LayaTransitionError)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))


@router.post("/tasks", response_model=LayaTaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    data: LayaTaskCreate,
    actor: FounderUser,
    session: SessionDependency,
    _csrf_guard: Annotated[None, Depends(_csrf)] = None,
) -> LayaTaskRead:
    try:
        return await LayaService(session).create(data, actor=actor)
    except LayaError as error:
        raise _error(error) from error


@router.get("/tasks", response_model=list[LayaTaskRead])
async def list_tasks(
    actor: FounderUser,
    session: SessionDependency,
    status_filter: Annotated[LayaTaskStatus | None, Query(alias="status")] = None,
) -> list[LayaTaskRead]:
    del actor
    return await LayaService(session).list(status_filter)


@router.get("/graph", response_model=LayaGraphSummary)
async def graph(actor: FounderUser, session: SessionDependency) -> LayaGraphSummary:
    del actor
    return await LayaService(session).summary()


@router.get("/tasks/{key}", response_model=LayaTaskRead)
async def read_task(key: str, actor: FounderUser, session: SessionDependency) -> LayaTaskRead:
    del actor
    try:
        return await LayaService(session).read(key)
    except LayaError as error:
        raise _error(error) from error


@router.post("/tasks/{key}/dependencies", response_model=LayaTaskRead)
async def add_dependency(
    key: str,
    data: LayaDependencyCreate,
    actor: FounderUser,
    session: SessionDependency,
    _csrf_guard: Annotated[None, Depends(_csrf)] = None,
) -> LayaTaskRead:
    try:
        return await LayaService(session).add_dependency(key, data.depends_on, actor=actor)
    except LayaError as error:
        raise _error(error) from error


@router.post("/tasks/{key}/transition", response_model=LayaTaskRead)
async def transition(
    key: str,
    data: LayaTransitionRequest,
    actor: FounderUser,
    session: SessionDependency,
    _csrf_guard: Annotated[None, Depends(_csrf)] = None,
) -> LayaTaskRead:
    try:
        return await LayaService(session).transition(
            key, data.status, actor=actor, blocker=data.blocker
        )
    except LayaError as error:
        raise _error(error) from error


@router.post("/tasks/{key}/evidence", response_model=LayaTaskRead)
async def add_evidence(
    key: str,
    data: LayaEvidenceCreate,
    actor: FounderUser,
    session: SessionDependency,
    _csrf_guard: Annotated[None, Depends(_csrf)] = None,
) -> LayaTaskRead:
    try:
        return await LayaService(session).add_evidence(key, data, actor=actor)
    except LayaError as error:
        raise _error(error) from error


@router.post("/tasks/{key}/failures", response_model=LayaFailureOutcome)
async def record_failure(
    key: str,
    data: LayaFailureReport,
    actor: FounderUser,
    session: SessionDependency,
    _csrf_guard: Annotated[None, Depends(_csrf)] = None,
) -> LayaFailureOutcome:
    try:
        task, action = await LayaService(session).record_failure(key, data, actor=actor)
    except LayaError as error:
        raise _error(error) from error
    return LayaFailureOutcome(task=task, recovery_action=action)
