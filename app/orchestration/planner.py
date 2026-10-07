from __future__ import annotations

from datetime import datetime, timezone
import re

from app.core.text import normalise_for_matching
from app.orchestration.health import HealthContract
from app.market.instruments import InstrumentResolver
from app.orchestration.policy import OrchestrationPolicy
from app.orchestration.schemas import (
    ExecutionPlan,
    OrchestrationIntent,
    PlanMode,
    PlanStep,
    PlanTarget,
)


class OrchestrationPlanner(HealthContract):
    component_name = "planner"

    def __init__(self, policy: OrchestrationPolicy | None = None) -> None:
        self.policy = policy or OrchestrationPolicy()

    def plan(
        self,
        intent: OrchestrationIntent,
        content: str,
        *,
        mode: PlanMode = PlanMode.SEQUENTIAL,
    ) -> ExecutionPlan:
        steps: list[PlanStep] = []
        live_step = self._live_data_step(content)
        if live_step is not None:
            steps.append(live_step)
        elif intent is OrchestrationIntent.PROJECTS:
            steps.append(
                PlanStep(target=PlanTarget.TOOL, name="project.analytics")
            )
        elif intent is OrchestrationIntent.PORTFOLIO:
            steps.append(
                PlanStep(target=PlanTarget.TOOL, name="portfolio.summary")
            )
        elif intent is OrchestrationIntent.TASK:
            steps.append(
                PlanStep(target=PlanTarget.TOOL, name="task.search")
            )
        elif intent is OrchestrationIntent.SEARCH:
            steps.append(
                PlanStep(
                    target=PlanTarget.INTEGRATION,
                    name="search",
                    operation="web_search",
                    payload={"query": content},
                )
            )
        elif intent is OrchestrationIntent.QUANT:
            steps.append(
                PlanStep(
                    target=PlanTarget.BACKGROUND,
                    name="quant_research_summary",
                )
            )
        elif intent is OrchestrationIntent.EXECUTION:
            steps.append(
                PlanStep(target=PlanTarget.AGENT, name="mock")
            )
        steps.append(PlanStep(target=PlanTarget.RESPONSE, name="assemble"))
        return ExecutionPlan(
            intent=intent,
            mode=mode,
            steps=steps,
            policies=self.policy.execution_policies,
            created_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _live_data_step(content: str) -> PlanStep | None:
        # Match on a normalised key; resolve instruments from the original
        # text so identifiers are never rewritten.
        value = normalise_for_matching(content)
        resolved = InstrumentResolver().resolve(content)
        if resolved is not None and (
            OrchestrationPlanner._is_live_market_request(value)
            or OrchestrationPlanner._is_bare_quote_request(value)
        ):
            return PlanStep(
                target=PlanTarget.TOOL,
                name="market.current_price",
                payload={"instrument": resolved.canonical.value},
            )
        if "weather" in value:
            match = re.search(
                r"\b(?:in|at|for)\s+([a-z][a-z .,'-]{1,100})",
                content,
                re.IGNORECASE,
            )
            location = match.group(1).strip(" .,?!") if match else None
            if location is not None:
                location = re.sub(
                    r"\s+\b(?:today|now|currently|right now)\b.*$",
                    "",
                    location,
                    flags=re.IGNORECASE,
                ).strip(" .,?!") or None
            return PlanStep(target=PlanTarget.TOOL, name="weather.current", payload={"location": location})
        if "date" in value or ("day" in value and "today" in value):
            return PlanStep(
                target=PlanTarget.TOOL,
                name="runtime.current_date",
            )
        return None

    @staticmethod
    def _is_live_market_request(value: str) -> bool:
        conceptual_markers = (
            "factor",
            "affect",
            "volatile",
            "volatility",
            "market cycle",
            "عوامل",
            "تأثیر",
            "تاثیر",
            "نوسان",
            "چرخه",
        )
        if any(marker in value for marker in conceptual_markers):
            return False
        explicit_live_markers = (
            "current",
            "currently",
            "latest",
            "right now",
            "at the moment",
            "today",
            "how much",
            "trading",
            "price",
            "doing",
            "quote",
            "فعلی",
            "کنونی",
            "الان",
            "امروز",
            "آخرین",
            "چنده",
            "چقدر",
            "معامله",
            "قیمت",
            # Finglish (transliterated Persian) price questions.
            "chande",
            "cheghadre",
            "gheymat",
            "qeymat",
            "ghimat",
        )
        return any(marker in value for marker in explicit_live_markers)

    _BARE_QUOTE = re.compile(
        r"^(?:what's|how's|where's)\s+(?:the\s+)?(?P<subject>.+?)[\s?.!]*$"
    )

    @staticmethod
    def _is_bare_quote_request(value: str) -> bool:
        """``What's FTSE 100?`` style: a contraction followed only by an alias."""
        match = OrchestrationPlanner._BARE_QUOTE.match(value)
        return (
            match is not None
            and InstrumentResolver().resolve_exact(match["subject"]) is not None
        )
