from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.laya.schemas import LayaGraphSummary


class BrainSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BrainAgentStatus(BrainSchema):
    default_agent: str | None
    default_agent_active: bool
    active_agents: int
    workspaces: int
    workspaces_with_default_grant: int


class BrainProviderStatus(BrainSchema):
    ai_execution_enabled: bool
    default_provider: str
    default_model: str
    available: bool
    message: str
    placeholder_adapters: list[str]
    embeddings_available: bool


class BrainKnowledgeStatus(BrainSchema):
    enabled_sources: int
    sources_by_reliability: dict[str, int]
    documents: int
    stale_time_sensitive_sources: int
    retrievals_last_24h: int


class BrainMarketStatus(BrainSchema):
    providers: list[str]
    credentials_present: bool
    customer_display_entitled: bool


class BrainGap(BrainSchema):
    code: str
    area: str
    detail: str


class BrainStatus(BrainSchema):
    generated_at: datetime
    execution_policy: dict[str, object]
    agents: BrainAgentStatus
    providers: BrainProviderStatus
    knowledge: BrainKnowledgeStatus
    market: BrainMarketStatus
    news_provider: str
    laya: LayaGraphSummary
    gaps: list[BrainGap]
