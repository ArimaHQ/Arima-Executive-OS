from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    AIRetrievedContext,
    AIWorkspaceRun,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentStatus,
    KnowledgeSource,
    KnowledgeSourceReliability,
    User,
)
from app.intelligence.access import (
    IntelligenceAccessError,
    require_workspace_membership,
)
from app.intelligence.ingestion import _as_utc
from app.intelligence.schemas import (
    KnowledgeSearchResult,
    RetrievalQuery,
    RetrievedKnowledge,
)

# Reliability orders evidence; it never admits evidence that failed the
# provenance, freshness, or tenancy filters.
RELIABILITY_WEIGHT: dict[KnowledgeSourceReliability, float] = {
    KnowledgeSourceReliability.OFFICIAL: 1.0,
    KnowledgeSourceReliability.PRIMARY: 0.95,
    KnowledgeSourceReliability.ESTABLISHED: 0.9,
    KnowledgeSourceReliability.USER_PROVIDED: 0.8,
    KnowledgeSourceReliability.UNVERIFIED: 0.7,
}
CORROBORATION_BONUS = 0.05
MAX_CORROBORATING_SOURCES = 3


def _terms(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{2,}", value.lower()))


@dataclass(frozen=True, slots=True)
class _Candidate:
    score: float
    chunk: KnowledgeChunk
    document: KnowledgeDocument
    source: KnowledgeSource
    corroborating_sources: int


def _score(overlap: float, reliability: KnowledgeSourceReliability, corroborating: int) -> float:
    bonus = 1 + CORROBORATION_BONUS * min(corroborating, MAX_CORROBORATING_SOURCES)
    return round(min(1.0, overlap * RELIABILITY_WEIGHT[reliability] * bonus), 6)


class TenantSafeRetrievalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def retrieve(
        self,
        *,
        workspace_id: UUID,
        run_id: UUID,
        actor: User,
        query: RetrievalQuery,
        now: datetime | None = None,
    ) -> tuple[RetrievedKnowledge, ...]:
        await require_workspace_membership(self.session, actor, workspace_id)
        binding = await self.session.scalar(
            select(AIWorkspaceRun).where(
                AIWorkspaceRun.workspace_id == workspace_id,
                AIWorkspaceRun.run_id == run_id,
                AIWorkspaceRun.user_id == actor.id,
            )
        )
        if binding is None:
            raise IntelligenceAccessError("AI run is not owned by this workspace")

        candidates = await self._candidates(workspace_id, query, now)
        results: list[RetrievedKnowledge] = []
        for rank, candidate in enumerate(candidates[: query.limit], start=1):
            evidence = AIRetrievedContext(
                workspace_id=workspace_id,
                run_id=run_id,
                chunk_id=candidate.chunk.id,
                rank=rank,
                score=candidate.score,
                source_observed_at=candidate.document.source_observed_at,
                provenance=candidate.document.provenance,
            )
            self.session.add(evidence)
            await self.session.flush()
            results.append(
                RetrievedKnowledge(
                    evidence_id=evidence.id,
                    chunk_id=candidate.chunk.id,
                    document_id=candidate.document.id,
                    source_id=candidate.source.id,
                    content=candidate.chunk.content,
                    rank=rank,
                    score=candidate.score,
                    source_observed_at=_as_utc(candidate.document.source_observed_at),
                    provenance=candidate.document.provenance,
                )
            )
        await self.session.commit()
        return tuple(results)

    async def search(
        self,
        *,
        workspace_id: UUID,
        actor: User,
        query: RetrievalQuery,
        now: datetime | None = None,
    ) -> tuple[KnowledgeSearchResult, ...]:
        """Read-only memory search: same filters as retrieval, no run evidence."""
        await require_workspace_membership(self.session, actor, workspace_id)
        candidates = await self._candidates(workspace_id, query, now)
        return tuple(
            KnowledgeSearchResult(
                rank=rank,
                score=candidate.score,
                chunk_id=candidate.chunk.id,
                document_id=candidate.document.id,
                source_id=candidate.source.id,
                source_name=candidate.source.name,
                reliability=candidate.source.reliability,
                title=candidate.document.title,
                content=candidate.chunk.content,
                source_observed_at=_as_utc(candidate.document.source_observed_at),
                expires_at=(
                    _as_utc(candidate.document.expires_at)
                    if candidate.document.expires_at is not None
                    else None
                ),
                provenance=candidate.document.provenance,
                corroborating_source_count=candidate.corroborating_sources,
            )
            for rank, candidate in enumerate(candidates[: query.limit], start=1)
        )

    async def _candidates(
        self,
        workspace_id: UUID,
        query: RetrievalQuery,
        now: datetime | None,
    ) -> list[_Candidate]:
        rows = (
            await self.session.execute(
                select(KnowledgeChunk, KnowledgeDocument, KnowledgeSource)
                .join(
                    KnowledgeDocument,
                    KnowledgeDocument.id == KnowledgeChunk.document_id,
                )
                .join(
                    KnowledgeSource, KnowledgeSource.id == KnowledgeDocument.source_id
                )
                .where(
                    KnowledgeChunk.workspace_id == workspace_id,
                    KnowledgeDocument.workspace_id == workspace_id,
                    KnowledgeSource.workspace_id == workspace_id,
                    KnowledgeDocument.status == KnowledgeDocumentStatus.INGESTED,
                    KnowledgeSource.is_enabled.is_(True),
                )
            )
        ).all()
        sources_per_hash = await self._sources_per_content_hash(workspace_id)
        query_terms = _terms(query.text)
        checked_at = _as_utc(now or datetime.now(UTC))
        candidates: list[_Candidate] = []
        for chunk, document, source in rows:
            if not document.provenance:
                continue
            if self._is_stale(document, source, checked_at):
                continue
            if (
                query.require_fresh
                and not source.freshness_required
                and document.expires_at is None
            ):
                continue
            overlap = len(query_terms.intersection(_terms(chunk.content)))
            if overlap:
                corroborating = max(0, sources_per_hash.get(document.content_hash, 1) - 1)
                candidates.append(
                    _Candidate(
                        score=_score(
                            overlap / max(1, len(query_terms)),
                            source.reliability,
                            corroborating,
                        ),
                        chunk=chunk,
                        document=document,
                        source=source,
                        corroborating_sources=corroborating,
                    )
                )
        candidates.sort(key=lambda item: (-item.score, item.chunk.ordinal))
        return candidates

    async def _sources_per_content_hash(self, workspace_id: UUID) -> dict[str, int]:
        rows = await self.session.execute(
            select(
                KnowledgeDocument.content_hash,
                func.count(func.distinct(KnowledgeDocument.source_id)),
            )
            .where(KnowledgeDocument.workspace_id == workspace_id)
            .group_by(KnowledgeDocument.content_hash)
            .having(func.count(func.distinct(KnowledgeDocument.source_id)) > 1)
        )
        return {content_hash: count for content_hash, count in rows.all()}

    @staticmethod
    def _is_stale(
        document: KnowledgeDocument,
        source: KnowledgeSource,
        now: datetime,
    ) -> bool:
        observed_at = _as_utc(document.source_observed_at)
        if document.expires_at is not None and _as_utc(document.expires_at) <= now:
            return True
        if source.freshness_required:
            if source.max_age_seconds is None:
                return True
            return observed_at + timedelta(seconds=source.max_age_seconds) <= now
        return False
