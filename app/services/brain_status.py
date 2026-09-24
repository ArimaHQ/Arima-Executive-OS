"""Jarvis Brain status: one founder view over the single ARIMA Brain.

Every value is read from persisted rows or configuration presence. Nothing is
estimated, and only platform aggregates are returned: no tenant names,
document titles, or content. Gaps are derived from the same state so Jarvis
can hand them to Laya as tasks.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.execution_policy import EXECUTION_POLICY
from app.database.models import (
    AgentDefinition,
    AgentStatus,
    AIRetrievedContext,
    KnowledgeDocument,
    KnowledgeDocumentStatus,
    KnowledgeSource,
    KnowledgeSourceReliability,
    Workspace,
    WorkspaceAgentGrant,
)
from app.laya.service import LayaService
from app.market.config import get_market_data_configurations
from app.providers.factory import ProviderFactory
from app.schemas.brain import (
    BrainAgentStatus,
    BrainGap,
    BrainKnowledgeStatus,
    BrainMarketStatus,
    BrainProviderStatus,
    BrainStatus,
)

# Adapters that exist only as placeholders; kept explicit so Jarvis reports
# them as model gaps rather than silently treating them as available.
PLACEHOLDER_PROVIDERS = ("anthropic", "ollama")


class BrainStatusService:
    def __init__(self, session: AsyncSession, *, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    async def status(self, *, now: datetime | None = None) -> BrainStatus:
        checked_at = now or datetime.now(UTC)
        agents = await self._agents()
        providers = await self._providers()
        knowledge = await self._knowledge(checked_at)
        market = self._market()
        laya = await LayaService(self.session).summary(now=checked_at)
        return BrainStatus(
            generated_at=checked_at,
            execution_policy=EXECUTION_POLICY.as_dict(),
            agents=agents,
            providers=providers,
            knowledge=knowledge,
            market=market,
            news_provider="not_configured",
            laya=laya,
            gaps=self._gaps(agents, providers, knowledge, market),
        )

    async def _agents(self) -> BrainAgentStatus:
        default = await self.session.scalar(
            select(AgentDefinition).where(
                AgentDefinition.is_default.is_(True),
                AgentDefinition.archived_at.is_(None),
            )
        )
        active = await self.session.scalar(
            select(func.count(AgentDefinition.id)).where(
                AgentDefinition.status == AgentStatus.ACTIVE
            )
        )
        workspaces = await self.session.scalar(select(func.count(Workspace.id)))
        granted = 0
        if default is not None:
            granted = await self.session.scalar(
                select(func.count(func.distinct(WorkspaceAgentGrant.workspace_id))).where(
                    WorkspaceAgentGrant.agent_id == default.id,
                    WorkspaceAgentGrant.revoked_at.is_(None),
                )
            ) or 0
        return BrainAgentStatus(
            default_agent=default.slug if default is not None else None,
            default_agent_active=default is not None and default.status is AgentStatus.ACTIVE,
            active_agents=active or 0,
            workspaces=workspaces or 0,
            workspaces_with_default_grant=granted,
        )

    async def _providers(self) -> BrainProviderStatus:
        available = False
        message = "AI execution is disabled"
        if self.settings.ai_execution_enabled:
            registry = ProviderFactory(settings=self.settings).build_registry()
            adapters = registry.list()
            if adapters:
                health = await adapters[0].health()
                available = health.available
                message = health.message
        return BrainProviderStatus(
            ai_execution_enabled=self.settings.ai_execution_enabled,
            default_provider=self.settings.default_provider,
            default_model=self.settings.default_model,
            available=available,
            message=message,
            placeholder_adapters=list(PLACEHOLDER_PROVIDERS),
            embeddings_available=False,
        )

    async def _knowledge(self, now: datetime) -> BrainKnowledgeStatus:
        by_reliability = {item.value: 0 for item in KnowledgeSourceReliability}
        for reliability, count in (
            await self.session.execute(
                select(KnowledgeSource.reliability, func.count(KnowledgeSource.id))
                .where(KnowledgeSource.is_enabled.is_(True))
                .group_by(KnowledgeSource.reliability)
            )
        ).all():
            by_reliability[reliability.value] = count
        documents = await self.session.scalar(
            select(func.count(KnowledgeDocument.id)).where(
                KnowledgeDocument.status == KnowledgeDocumentStatus.INGESTED
            )
        )
        latest = (
            select(
                KnowledgeDocument.source_id,
                func.max(KnowledgeDocument.source_observed_at).label("latest"),
            )
            .group_by(KnowledgeDocument.source_id)
            .subquery()
        )
        stale = 0
        for max_age, observed in (
            await self.session.execute(
                select(KnowledgeSource.max_age_seconds, latest.c.latest)
                .outerjoin(latest, latest.c.source_id == KnowledgeSource.id)
                .where(
                    KnowledgeSource.is_enabled.is_(True),
                    KnowledgeSource.freshness_required.is_(True),
                )
            )
        ).all():
            if observed is None or max_age is None:
                stale += 1
                continue
            observed_at = observed if observed.tzinfo else observed.replace(tzinfo=UTC)
            if observed_at + timedelta(seconds=max_age) <= now:
                stale += 1
        retrievals = await self.session.scalar(
            select(func.count(AIRetrievedContext.id)).where(
                AIRetrievedContext.retrieved_at >= now - timedelta(hours=24)
            )
        )
        return BrainKnowledgeStatus(
            enabled_sources=sum(by_reliability.values()),
            sources_by_reliability=by_reliability,
            documents=documents or 0,
            stale_time_sensitive_sources=stale,
            retrievals_last_24h=retrievals or 0,
        )

    @staticmethod
    def _market() -> BrainMarketStatus:
        configurations = get_market_data_configurations()
        return BrainMarketStatus(
            providers=[item.provider.value for item in configurations],
            credentials_present=any(item.api_key is not None for item in configurations),
            customer_display_entitled=any(
                item.customer_display_entitled for item in configurations
            ),
        )

    @staticmethod
    def _gaps(
        agents: BrainAgentStatus,
        providers: BrainProviderStatus,
        knowledge: BrainKnowledgeStatus,
        market: BrainMarketStatus,
    ) -> list[BrainGap]:
        gaps: list[BrainGap] = []

        def add(code: str, area: str, detail: str) -> None:
            gaps.append(BrainGap(code=code, area=area, detail=detail))

        if agents.default_agent is None or not agents.default_agent_active:
            add("agent_platform_not_bootstrapped", "brain", "No active default agent; run agent bootstrap.")
        elif agents.workspaces_with_default_grant < agents.workspaces:
            add(
                "workspaces_without_agent_grant",
                "brain",
                f"{agents.workspaces - agents.workspaces_with_default_grant} workspace(s) lack an active default-agent grant.",
            )
        if not providers.available:
            add("llm_provider_unavailable", "model", providers.message)
        add("local_model_adapter_placeholder", "model", "Ollama/Qwen and Anthropic adapters are placeholders.")
        if not providers.embeddings_available:
            add("semantic_memory_unavailable", "memory", "No embedding provider or pgvector index; retrieval is lexical.")
        if knowledge.sources_by_reliability[KnowledgeSourceReliability.OFFICIAL.value] == 0:
            add("no_official_sources", "research", "No official-tier source is ingested (e.g. central bank, statistics office).")
        if knowledge.stale_time_sensitive_sources:
            add(
                "stale_time_sensitive_sources",
                "research",
                f"{knowledge.stale_time_sensitive_sources} time-sensitive source(s) are stale or empty.",
            )
        add("news_provider_not_configured", "research", "No verified news/macro provider; QLab signals stay NEWS_BLOCKED.")
        if not market.credentials_present or not market.customer_display_entitled:
            add("market_data_unverified", "data", "No credentialed, entitlement-verified market-data provider.")
        add("risk_inputs_unavailable", "risk", "No authoritative daily-loss or strategy-exposure source; risk fails closed.")
        return gaps
