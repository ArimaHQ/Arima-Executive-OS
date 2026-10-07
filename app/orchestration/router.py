from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.brain.laya_client import LayaClient, LayaStatus
from app.core.text import normalise_for_matching
from app.orchestration.exceptions import RoutingError
from app.orchestration.health import HealthContract
from app.orchestration.schemas import (
    AgentCandidate,
    ModelProfile,
    OrchestrationIntent,
    OrchestrationRequest,
)
from app.providers.base import ProviderAdapter
from app.providers.registry import ProviderRegistry
from app.providers.types import ProviderCapability


class IntentEngine(HealthContract):
    component_name = "intent"

    EXECUTIVE_FOCUS_PHRASES = (
        "what should i focus on today",
        "what are my priorities today",
        "what needs my attention",
        "what should i work on next",
        "what are the most important things today",
    )

    KEYWORDS = {
        OrchestrationIntent.PORTFOLIO: ("portfolio", "holdings"),
        OrchestrationIntent.QUANT: ("quant", "backtest", "signal"),
        OrchestrationIntent.GROWTH: ("growth", "content", "campaign"),
        OrchestrationIntent.PROJECTS: ("project", "milestone"),
        OrchestrationIntent.SEARCH: ("search", "find", "look up"),
        OrchestrationIntent.PLANNING: ("plan", "roadmap"),
        OrchestrationIntent.ANALYSIS: ("analyse", "analyze", "compare"),
        OrchestrationIntent.EXECUTION: ("execute", "run", "do"),
        OrchestrationIntent.TASK: ("task", "todo"),
        OrchestrationIntent.CONVERSATION: ("chat", "discuss"),
    }

    # Markers are matched against ``normalise_for_matching`` output, so
    # typographic apostrophes and Arabic yeh/kaf variants need no duplicates.
    _CURRENT_NEWS_MARKERS = (
        "news today",
        "news stories today",
        "today's news",
        "latest news",
        "current news",
        "اخبار امروز",
        "آخرین اخبار",
        "جدیدترین اخبار",
    )

    _ASSET_DISCUSSION_MARKERS = (
        "explain what factors",
        "what factors affect",
        "what affects",
        "why is",
        "why are",
        "volatile",
        "volatility",
        "market cycles",
        "in simple terms",
        "به زبان ساده",
        "عوامل",
        "تأثیر",
        "تاثیر",
        "نوسان",
        "چرخه",
        "چرا",
    )

    # Laya only chooses among these; explicit requests and the curated news /
    # asset-discussion markers stay deterministic.
    LAYA_QUESTIONS: dict[str, Any] = {
        "intent": {
            "type": "choice",
            "instructions": (
                "What does the user want the executive assistant to do?"
            ),
            "criteria": {
                OrchestrationIntent.PORTFOLIO.value: (
                    "review or change investment holdings or a portfolio"
                ),
                OrchestrationIntent.QUANT.value: (
                    "quantitative analysis, backtests, trading signals"
                ),
                OrchestrationIntent.GROWTH.value: (
                    "marketing, content, campaigns, audience growth"
                ),
                OrchestrationIntent.PROJECTS.value: (
                    "project status, milestones, deliverables"
                ),
                OrchestrationIntent.SEARCH.value: (
                    "find or look up information"
                ),
                OrchestrationIntent.PLANNING.value: (
                    "plans, roadmaps, goals, forecasting"
                ),
                OrchestrationIntent.ANALYSIS.value: (
                    "analyse, compare or research something"
                ),
                OrchestrationIntent.EXECUTION.value: (
                    "carry out an action or run an operation"
                ),
                OrchestrationIntent.TASK.value: (
                    "create or manage tasks and to-dos"
                ),
                OrchestrationIntent.CONVERSATION.value: (
                    "discuss or talk something through"
                ),
                OrchestrationIntent.GENERAL.value: (
                    "greeting or anything that fits none of the above"
                ),
            },
        }
    }

    # Laya may recognise these but never originates them: an action-bearing
    # route is only reachable through explicit intent or the deterministic
    # rules, exactly as before Laya existed.
    LAYA_DEFERRED_INTENTS = frozenset({OrchestrationIntent.EXECUTION})

    def __init__(
        self,
        laya: LayaClient | None = None,
        *,
        min_confidence: float = 0.6,
    ) -> None:
        self.laya = laya
        self.min_confidence = min_confidence

    async def resolve(
        self, request: OrchestrationRequest
    ) -> OrchestrationIntent:
        """Resolve intent: explicit > deterministic > Laya > keyword.

        Records why in ``request.metadata``: ``intent_source`` is one of
        ``explicit``, ``deterministic``, ``laya``, ``keyword`` or ``fallback``
        (no rule matched, so the safe ``general`` intent was used), and
        ``laya_status`` says what happened to the Laya consultation.
        """
        metadata = request.metadata
        if request.requested_intent is not None:
            metadata["intent_source"] = IntentSource.EXPLICIT
            metadata["laya_status"] = LayaDecision.SKIPPED
            return request.requested_intent
        content = normalise_for_matching(request.content)
        deterministic = self._deterministic(content)
        if deterministic is not None:
            metadata["intent_source"] = IntentSource.DETERMINISTIC
            metadata["laya_status"] = LayaDecision.SKIPPED
            return deterministic
        if self.laya is None:
            metadata["laya_status"] = LayaDecision.DISABLED
        else:
            laya_intent = await self._laya_intent(request)
            if laya_intent is not None:
                metadata["intent_source"] = IntentSource.LAYA
                return laya_intent
        keyword = self._keyword_intent(content)
        metadata["intent_source"] = (
            IntentSource.FALLBACK if keyword is None else IntentSource.KEYWORD
        )
        return keyword or OrchestrationIntent.GENERAL

    async def _laya_intent(
        self, request: OrchestrationRequest
    ) -> OrchestrationIntent | None:
        assert self.laya is not None
        result = await self.laya.predict(request.content, self.LAYA_QUESTIONS)
        request.metadata["laya_latency_ms"] = result.latency_ms
        if result.status is not LayaStatus.OK:
            request.metadata["laya_status"] = result.status.value
            return None
        answer = (result.answers or {}).get("intent")
        choice = answer.get("choice") if isinstance(answer, dict) else None
        confidence = (
            answer.get("confidence") if isinstance(answer, dict) else None
        )
        if not isinstance(choice, str) or not _valid_confidence(confidence):
            request.metadata["laya_status"] = LayaStatus.MALFORMED.value
            return None
        if choice not in self.LAYA_QUESTIONS["intent"]["criteria"]:
            # Not one of the choices we offered: never guess an intent.
            request.metadata["laya_status"] = LayaDecision.INVALID_INTENT
            return None
        request.metadata["laya_confidence"] = confidence
        if confidence < self.min_confidence:
            request.metadata["laya_status"] = LayaDecision.LOW_CONFIDENCE
            return None
        intent = OrchestrationIntent(choice)
        if intent in self.LAYA_DEFERRED_INTENTS:
            request.metadata["laya_status"] = LayaDecision.DEFERRED
            return None
        request.metadata["laya_status"] = LayaStatus.OK.value
        return intent

    def _deterministic(self, content: str) -> OrchestrationIntent | None:
        if any(marker in content for marker in self._CURRENT_NEWS_MARKERS):
            return OrchestrationIntent.CURRENT_NEWS
        if any(marker in content for marker in self._ASSET_DISCUSSION_MARKERS):
            return OrchestrationIntent.GENERAL_ASSET_DISCUSSION
        return None

    def detect(self, request: OrchestrationRequest) -> OrchestrationIntent:
        """Synchronous deterministic detection (no Laya)."""
        if request.requested_intent is not None:
            return request.requested_intent
        content = normalise_for_matching(request.content)
        return (
            self._deterministic(content)
            or self._keyword_intent(content)
            or OrchestrationIntent.GENERAL
        )

    def _keyword_intent(self, content: str) -> OrchestrationIntent | None:
        for intent, keywords in self.KEYWORDS.items():
            if any(keyword in content for keyword in keywords):
                return intent
        return None

    @classmethod
    def is_executive_focus(cls, request: OrchestrationRequest) -> bool:
        content = normalise_for_matching(request.content)
        return any(phrase in content for phrase in cls.EXECUTIVE_FOCUS_PHRASES)


class IntentSource:
    EXPLICIT = "explicit"
    DETERMINISTIC = "deterministic"
    LAYA = "laya"
    KEYWORD = "keyword"
    FALLBACK = "fallback"


class LayaDecision:
    """``laya_status`` values beyond the transport-level ``LayaStatus``."""

    SKIPPED = "skipped"
    DISABLED = "disabled"
    LOW_CONFIDENCE = "low_confidence"
    INVALID_INTENT = "invalid_intent"
    DEFERRED = "deferred"


def _valid_confidence(value: Any) -> bool:
    # bool is an int subclass; NaN/inf fail the range check.
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0.0 <= value <= 1.0
    )


class AgentRouter(HealthContract):
    component_name = "agent_router"

    def select(
        self,
        candidates: tuple[AgentCandidate, ...],
        intent: OrchestrationIntent,
    ) -> AgentCandidate:
        eligible = [
            candidate
            for candidate in candidates
            if candidate.available
            and candidate.healthy
            and candidate.permission_granted
        ]
        if not eligible:
            raise RoutingError("No eligible agent is available")

        def score(candidate: AgentCandidate) -> tuple[int, Decimal, str]:
            capability_score = 100 if intent in candidate.capabilities else 0
            return (
                capability_score + candidate.priority,
                -candidate.estimated_cost,
                candidate.name,
            )

        return max(eligible, key=score)


class ProviderRouter(HealthContract):
    component_name = "provider_router"

    def __init__(self, registry: ProviderRegistry) -> None:
        self.registry = registry

    async def select(
        self,
        required: frozenset[ProviderCapability],
    ) -> ProviderAdapter:
        candidates = self.registry.find(capabilities=required)
        healthy: list[tuple[int, str, ProviderAdapter]] = []
        for adapter in candidates:
            status = await adapter.health()
            if status.available:
                healthy.append(
                    (
                        status.latency_ms or 0,
                        adapter.provider.value,
                        adapter,
                    )
                )
        if not healthy:
            raise RoutingError("No healthy provider matches capabilities")
        return min(healthy, key=lambda item: (item[0], item[1]))[2]


class ModelRouter(HealthContract):
    component_name = "model_router"

    def select(
        self,
        provider: ProviderAdapter,
        profile: ModelProfile,
    ) -> str:
        requirements = {
            ModelProfile.VISION_READY: lambda model: provider.supports_images(
                model
            ),
            ModelProfile.TOOL_READY: lambda model: provider.supports_tools(
                model
            ),
            ModelProfile.JSON_READY: lambda model: (
                provider.supports_json_mode(model)
            ),
        }
        predicate = requirements.get(profile, lambda model: True)
        for model in provider.models:
            if predicate(model):
                return model
        raise RoutingError(
            f"No model matches orchestration profile {profile.value}"
        )
