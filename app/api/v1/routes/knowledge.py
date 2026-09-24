"""Workspace knowledge API: the Layer 1 entry point into shared Brain memory.

Sources and documents enter the same tenant-scoped knowledge store that the
Brain's retrieval reads from. Every write requires workspace membership and
CSRF, requires provenance, rejects credentials, and is audited.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.csrf import require_valid_csrf
from app.auth.dependencies import get_current_active_user
from app.database.models import AuditAction, AuditEntity, KnowledgeSource, User
from app.database.session import get_session
from app.intelligence.access import IntelligenceAccessError
from app.intelligence.ingestion import (
    KnowledgeIngestionService,
    KnowledgeValidationError,
)
from app.intelligence.retrieval import TenantSafeRetrievalService
from app.intelligence.schemas import (
    IngestedKnowledge,
    KnowledgeDocumentInput,
    KnowledgeSearchResult,
    KnowledgeSourceInput,
    KnowledgeSourceRead,
    RetrievalQuery,
)
from app.intelligence.sources import KnowledgeSourceCatalog
from app.services.audit import record_audit

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_active_user)]


def _csrf(request: Request) -> None:
    require_valid_csrf(request)


def _error(error: IntelligenceAccessError | KnowledgeValidationError) -> HTTPException:
    if isinstance(error, IntelligenceAccessError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))


async def _source_read(
    session: AsyncSession, workspace_id: UUID, source_id: UUID
) -> KnowledgeSourceRead:
    sources = await KnowledgeSourceCatalog(session).workspace_sources(workspace_id)
    return next(source for source in sources if source.id == source_id)


@router.post(
    "/workspaces/{workspace_id}/sources",
    response_model=KnowledgeSourceRead,
    status_code=status.HTTP_201_CREATED,
)
async def register_source(
    workspace_id: UUID,
    data: KnowledgeSourceInput,
    actor: CurrentUser,
    session: SessionDependency,
    _csrf_guard: Annotated[None, Depends(_csrf)] = None,
) -> KnowledgeSourceRead:
    existing_id = await session.scalar(
        select(KnowledgeSource.id).where(
            KnowledgeSource.workspace_id == workspace_id,
            KnowledgeSource.source_type == data.source_type,
            KnowledgeSource.external_id == data.external_id,
        )
    )
    try:
        source = await KnowledgeIngestionService(session).create_source(
            workspace_id=workspace_id, actor=actor, data=data
        )
    except (IntelligenceAccessError, KnowledgeValidationError) as error:
        raise _error(error) from error
    if existing_id is None:
        record_audit(
            session,
            actor_id=actor.id,
            action=AuditAction.CREATE,
            entity=AuditEntity.KNOWLEDGE_SOURCE,
            entity_id=source.id,
        )
        await session.commit()
    return await _source_read(session, workspace_id, source.id)


@router.get(
    "/workspaces/{workspace_id}/sources",
    response_model=list[KnowledgeSourceRead],
)
async def list_sources(
    workspace_id: UUID,
    actor: CurrentUser,
    session: SessionDependency,
) -> list[KnowledgeSourceRead]:
    try:
        return list(
            await KnowledgeSourceCatalog(session).list_sources(
                workspace_id=workspace_id, actor=actor
            )
        )
    except IntelligenceAccessError as error:
        raise _error(error) from error


@router.post(
    "/workspaces/{workspace_id}/sources/{source_id}/documents",
    response_model=IngestedKnowledge,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_document(
    workspace_id: UUID,
    source_id: UUID,
    data: KnowledgeDocumentInput,
    actor: CurrentUser,
    session: SessionDependency,
    _csrf_guard: Annotated[None, Depends(_csrf)] = None,
) -> IngestedKnowledge:
    try:
        result = await KnowledgeIngestionService(session).ingest(
            workspace_id=workspace_id, source_id=source_id, actor=actor, data=data
        )
    except (IntelligenceAccessError, KnowledgeValidationError) as error:
        raise _error(error) from error
    if not result.duplicate:
        record_audit(
            session,
            actor_id=actor.id,
            action=AuditAction.CREATE,
            entity=AuditEntity.KNOWLEDGE_DOCUMENT,
            entity_id=result.document_id,
        )
        await session.commit()
    return result


@router.get(
    "/workspaces/{workspace_id}/search",
    response_model=list[KnowledgeSearchResult],
)
async def search_knowledge(
    workspace_id: UUID,
    actor: CurrentUser,
    session: SessionDependency,
    q: Annotated[str, Query(min_length=1, max_length=2_000)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    require_fresh: bool = False,
) -> list[KnowledgeSearchResult]:
    try:
        return list(
            await TenantSafeRetrievalService(session).search(
                workspace_id=workspace_id,
                actor=actor,
                query=RetrievalQuery(text=q, limit=limit, require_fresh=require_fresh),
            )
        )
    except IntelligenceAccessError as error:
        raise _error(error) from error
