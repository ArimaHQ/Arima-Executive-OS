"""Workspace knowledge-source catalogue with health derived from real rows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    AIRetrievedContext,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentStatus,
    KnowledgeSource,
    User,
)
from app.intelligence.access import require_workspace_membership
from app.intelligence.ingestion import _as_utc
from app.intelligence.schemas import KnowledgeSourceHealth, KnowledgeSourceRead


class FreshnessState:
    NO_DOCUMENTS = "no_documents"
    FRESH = "fresh"
    STALE = "stale"
    NOT_TIME_SENSITIVE = "not_time_sensitive"
    DISABLED = "disabled"


class KnowledgeSourceCatalog:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_sources(
        self,
        *,
        workspace_id: UUID,
        actor: User,
        now: datetime | None = None,
    ) -> tuple[KnowledgeSourceRead, ...]:
        await require_workspace_membership(self.session, actor, workspace_id)
        return await self.workspace_sources(workspace_id, now=now)

    async def workspace_sources(
        self,
        workspace_id: UUID,
        *,
        now: datetime | None = None,
    ) -> tuple[KnowledgeSourceRead, ...]:
        """Catalogue for an already-authorized caller (membership or Founder)."""
        checked_at = _as_utc(now or datetime.now(UTC))
        sources = (
            await self.session.scalars(
                select(KnowledgeSource)
                .where(KnowledgeSource.workspace_id == workspace_id)
                .order_by(KnowledgeSource.created_at, KnowledgeSource.id)
            )
        ).all()
        documents = {
            source_id: (count, latest)
            for source_id, count, latest in (
                await self.session.execute(
                    select(
                        KnowledgeDocument.source_id,
                        func.count(KnowledgeDocument.id),
                        func.max(KnowledgeDocument.source_observed_at),
                    )
                    .where(
                        KnowledgeDocument.workspace_id == workspace_id,
                        KnowledgeDocument.status == KnowledgeDocumentStatus.INGESTED,
                    )
                    .group_by(KnowledgeDocument.source_id)
                )
            ).all()
        }
        retrievals = {
            source_id: (count, latest)
            for source_id, count, latest in (
                await self.session.execute(
                    select(
                        KnowledgeDocument.source_id,
                        func.count(AIRetrievedContext.id),
                        func.max(AIRetrievedContext.retrieved_at),
                    )
                    .join(KnowledgeChunk, KnowledgeChunk.id == AIRetrievedContext.chunk_id)
                    .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
                    .where(AIRetrievedContext.workspace_id == workspace_id)
                    .group_by(KnowledgeDocument.source_id)
                )
            ).all()
        }
        return tuple(
            self._read(source, documents.get(source.id), retrievals.get(source.id), checked_at)
            for source in sources
        )

    @staticmethod
    def _read(
        source: KnowledgeSource,
        documents: tuple[int, datetime | None] | None,
        retrievals: tuple[int, datetime | None] | None,
        now: datetime,
    ) -> KnowledgeSourceRead:
        document_count, latest = documents or (0, None)
        retrieval_count, last_retrieved = retrievals or (0, None)
        latest_observed = _as_utc(latest) if latest is not None else None
        if not source.is_enabled:
            state = FreshnessState.DISABLED
        elif document_count == 0 or latest_observed is None:
            state = FreshnessState.NO_DOCUMENTS
        elif not source.freshness_required:
            state = FreshnessState.NOT_TIME_SENSITIVE
        elif (
            source.max_age_seconds is not None
            and latest_observed + timedelta(seconds=source.max_age_seconds) > now
        ):
            state = FreshnessState.FRESH
        else:
            state = FreshnessState.STALE
        return KnowledgeSourceRead(
            id=source.id,
            workspace_id=source.workspace_id,
            source_type=source.source_type,
            external_id=source.external_id,
            name=source.name,
            source_uri=source.source_uri,
            reliability=source.reliability,
            authority=source.authority,
            freshness_required=source.freshness_required,
            max_age_seconds=source.max_age_seconds,
            is_enabled=source.is_enabled,
            created_at=_as_utc(source.created_at),
            health=KnowledgeSourceHealth(
                document_count=document_count,
                latest_observed_at=latest_observed,
                freshness_state=state,
                retrieval_count=retrieval_count,
                last_retrieved_at=(
                    _as_utc(last_retrieved) if last_retrieved is not None else None
                ),
            ),
        )
