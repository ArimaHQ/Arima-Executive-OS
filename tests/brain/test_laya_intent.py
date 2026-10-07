import asyncio
import json
import math
from typing import Any

import httpx
import pytest

from app.brain.laya_client import LayaClient
from app.core.config import Settings
from app.orchestration.router import IntentEngine
from app.orchestration.schemas import OrchestrationIntent, OrchestrationRequest

LAYA_URL = "http://laya.test/v1/systemone"
OFFERED = set(IntentEngine.LAYA_QUESTIONS["intent"]["criteria"])


def _client(
    answers: Any = None,
    *,
    status_code: int = 200,
    seen: list[dict[str, Any]] | None = None,
    error: Exception | None = None,
    api_key: str | None = None,
) -> LayaClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if error is not None:
            raise error
        if seen is not None:
            seen.append(
                {
                    "body": json.loads(request.content),
                    "authorization": request.headers.get("Authorization"),
                }
            )
        return httpx.Response(status_code, json={"answers": answers or {}})

    return LayaClient(
        LAYA_URL,
        api_key=api_key,
        timeout_seconds=1.0,
        transport=httpx.MockTransport(handler),
    )


def _intent_answer(choice: Any, confidence: Any) -> dict[str, Any]:
    return {
        "intent": {"type": "choice", "choice": choice, "confidence": confidence}
    }


def _resolve(engine: IntentEngine, content: str, **kwargs: Any):
    request = OrchestrationRequest(content=content, **kwargs)
    intent = asyncio.run(engine.resolve(request))
    return intent, request.metadata["intent_source"], request.metadata


# --- precedence -------------------------------------------------------------


def test_explicit_intent_wins_and_skips_laya() -> None:
    seen: list[dict[str, Any]] = []
    engine = IntentEngine(_client(_intent_answer("general", 0.99), seen=seen))

    intent, source, meta = _resolve(
        engine, "latest news on my portfolio", requested_intent=OrchestrationIntent.TASK
    )
    assert (intent, source) == (OrchestrationIntent.TASK, "explicit")
    assert meta["laya_status"] == "skipped"
    assert seen == []


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("What is the latest news today?", OrchestrationIntent.CURRENT_NEWS),
        ("Give me today’s news", OrchestrationIntent.CURRENT_NEWS),
        ("Give me todayʼs news", OrchestrationIntent.CURRENT_NEWS),
        ("اخبار امروز بازار", OrchestrationIntent.CURRENT_NEWS),
        ("Why is gold so volatile?", OrchestrationIntent.GENERAL_ASSET_DISCUSSION),
        ("چرا بیت کوين نوسان دارد؟", OrchestrationIntent.GENERAL_ASSET_DISCUSSION),
    ],
)
def test_deterministic_rules_win_and_skip_laya(
    content: str, expected: OrchestrationIntent
) -> None:
    seen: list[dict[str, Any]] = []
    engine = IntentEngine(_client(_intent_answer("portfolio", 0.99), seen=seen))

    intent, source, meta = _resolve(engine, content)
    assert (intent, source) == (expected, "deterministic")
    assert meta["laya_status"] == "skipped"
    assert seen == []


def test_confident_laya_answer_beats_keywords() -> None:
    engine = IntentEngine(_client(_intent_answer("portfolio", 0.9)))

    # "do" would otherwise match the EXECUTION keyword.
    intent, source, meta = _resolve(engine, "How do my holdings look?")
    assert (intent, source) == (OrchestrationIntent.PORTFOLIO, "laya")
    assert meta["laya_status"] == "ok"
    assert meta["laya_confidence"] == 0.9
    assert meta["laya_latency_ms"] >= 0


# --- confidence -------------------------------------------------------------


@pytest.mark.parametrize(
    ("confidence", "expected_source", "status"),
    [
        (0.6, "laya", "ok"),  # threshold is inclusive
        (1.0, "laya", "ok"),
        (0.5999, "keyword", "low_confidence"),
        (0.0, "keyword", "low_confidence"),
    ],
)
def test_confidence_threshold(confidence: float, expected_source: str, status: str) -> None:
    engine = IntentEngine(
        _client(_intent_answer("planning", confidence)), min_confidence=0.6
    )
    intent, source, meta = _resolve(engine, "Review my portfolio")
    assert source == expected_source
    assert meta["laya_status"] == status
    assert intent is (
        OrchestrationIntent.PLANNING if source == "laya" else OrchestrationIntent.PORTFOLIO
    )


@pytest.mark.parametrize(
    "confidence",
    [None, "0.99", True, math.nan, math.inf, -math.inf, 1.01, -0.1, [0.9], {"v": 1}],
)
def test_invalid_confidence_is_malformed(confidence: Any) -> None:
    engine = IntentEngine(_client(_intent_answer("portfolio", confidence)))
    intent, source, meta = _resolve(engine, "Make a roadmap plan")
    assert (intent, source) == (OrchestrationIntent.PLANNING, "keyword")
    assert meta["laya_status"] == "malformed"
    assert "laya_confidence" not in meta


@pytest.mark.parametrize(
    "answers",
    [
        {},
        {"intent": None},
        {"intent": "portfolio"},
        {"intent": {"confidence": 0.9}},
        {"intent": {"choice": None, "confidence": 0.9}},
        {"intent": {"choice": ["portfolio"], "confidence": 0.9}},
        {"intent": {"choice": 3, "confidence": 0.9}},
        {"other": {"choice": "portfolio", "confidence": 0.9}},
    ],
)
def test_malformed_answer_shapes_fall_back(answers: dict[str, Any]) -> None:
    engine = IntentEngine(_client(answers))
    intent, source, meta = _resolve(engine, "Run a quant backtest")
    assert (intent, source) == (OrchestrationIntent.QUANT, "keyword")
    assert meta["laya_status"] == "malformed"


# --- no hallucinated intents ------------------------------------------------


@pytest.mark.parametrize(
    "choice",
    ["teleport", "PORTFOLIO", " portfolio", "current_news", "general_asset_discussion"],
)
def test_choices_we_did_not_offer_are_rejected(choice: str) -> None:
    # current_news / general_asset_discussion are real intents but are owned
    # by deterministic rules, so Laya was never offered them.
    engine = IntentEngine(_client(_intent_answer(choice, 0.99)))
    intent, source, meta = _resolve(engine, "Show project milestones")
    assert (intent, source) == (OrchestrationIntent.PROJECTS, "keyword")
    assert meta["laya_status"] == "invalid_intent"


def test_offered_choices_are_real_intents() -> None:
    assert OFFERED <= {intent.value for intent in OrchestrationIntent}
    assert "current_news" not in OFFERED
    assert "general_asset_discussion" not in OFFERED


def test_laya_cannot_originate_execution() -> None:
    engine = IntentEngine(_client(_intent_answer("execution", 0.99)))
    intent, source, meta = _resolve(engine, "Sell all my BTC now")
    assert (intent, source) == (OrchestrationIntent.GENERAL, "fallback")
    assert meta["laya_status"] == "deferred"


def test_execution_keyword_path_is_unchanged_by_laya() -> None:
    engine = IntentEngine(_client(_intent_answer("execution", 0.99)))
    request = OrchestrationRequest(content="Execute the weekly report")
    assert asyncio.run(engine.resolve(request)) is engine.detect(request)
    assert request.metadata["intent_source"] == "keyword"


# --- failure modes ----------------------------------------------------------


@pytest.mark.parametrize(
    ("client", "status"),
    [
        (_client(error=httpx.ConnectError("refused")), "unavailable"),
        (_client(error=httpx.ReadTimeout("slow")), "timeout"),
        (_client(status_code=503), "unavailable"),
        (LayaClient("http://[bad-url", timeout_seconds=1.0), "unavailable"),
    ],
)
def test_laya_failures_fall_back_to_keywords(client: LayaClient, status: str) -> None:
    engine = IntentEngine(client)
    intent, source, meta = _resolve(engine, "Run a quant backtest")
    assert (intent, source) == (OrchestrationIntent.QUANT, "keyword")
    assert meta["laya_status"] == status


def test_no_rule_match_is_fallback_general() -> None:
    engine = IntentEngine(_client(error=httpx.ConnectError("refused")))
    intent, source, _ = _resolve(engine, "Hello there")
    assert (intent, source) == (OrchestrationIntent.GENERAL, "fallback")


def test_disabled_laya_matches_detect() -> None:
    engine = IntentEngine()
    for text, status in (
        ("Review my portfolio", "disabled"),
        ("Hello there", "disabled"),
        ("Show project milestones", "disabled"),
        ("What’s today’s news?", "skipped"),
        ("Why is gold volatile?", "skipped"),
    ):
        request = OrchestrationRequest(content=text)
        assert asyncio.run(engine.resolve(request)) == engine.detect(request)
        assert request.metadata["laya_status"] == status
        assert "laya_latency_ms" not in request.metadata


# --- multilingual -----------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "choice", "expected", "pinned"),
    [
        ("برای سه ماه آینده برنامه بریز", "planning", OrchestrationIntent.PLANNING, True),
        ("پورتفوی من را بررسی کن", "portfolio", OrchestrationIntent.PORTFOLIO, True),
        ("یک تسک برای جلسه فردا بساز", "task", OrchestrationIntent.TASK, True),
        ("barname-ye fasl-e ba'd ro benevis", "planning", OrchestrationIntent.PLANNING, False),
        ("portfolio-mo check kon lotfan", "portfolio", OrchestrationIntent.PORTFOLIO, False),
        ("بک‌تست استراتژی EURUSD رو اجرا کن", "quant", OrchestrationIntent.QUANT, True),
        ("How are my holdings doing?", "portfolio", OrchestrationIntent.PORTFOLIO, False),
    ],
)
def test_multilingual_requests_use_laya(
    text: str, choice: str, expected: OrchestrationIntent, pinned: bool
) -> None:
    seen: list[dict[str, Any]] = []
    engine = IntentEngine(_client(_intent_answer(choice, 0.8), seen=seen, api_key="k"))

    intent, source, _ = _resolve(engine, text)
    assert (intent, source) == (expected, "laya")
    assert ("model" in seen[0]["body"]) is pinned
    assert seen[0]["body"]["state"]["text"] == text  # tickers untouched
    assert seen[0]["authorization"] == "Bearer k"


def test_persian_without_laya_is_safe_fallback() -> None:
    engine = IntentEngine(_client(error=httpx.ConnectError("refused")))
    intent, source, _ = _resolve(engine, "برای سه ماه آینده برنامه بریز")
    assert (intent, source) == (OrchestrationIntent.GENERAL, "fallback")


# --- isolation --------------------------------------------------------------


def test_concurrent_requests_keep_their_own_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        text = json.loads(request.content)["state"]["text"]
        choice = "portfolio" if "holdings" in text else "planning"
        return httpx.Response(
            200, json={"answers": _intent_answer(choice, 0.9 if choice == "portfolio" else 0.2)}
        )

    engine = IntentEngine(
        LayaClient(LAYA_URL, transport=httpx.MockTransport(handler))
    )
    first = OrchestrationRequest(content="How are my holdings?")
    second = OrchestrationRequest(content="Make a roadmap plan")

    async def both():
        return await asyncio.gather(engine.resolve(first), engine.resolve(second))

    assert asyncio.run(both()) == [OrchestrationIntent.PORTFOLIO, OrchestrationIntent.PLANNING]
    assert first.metadata["intent_source"] == "laya"
    assert second.metadata["intent_source"] == "keyword"
    assert second.metadata["laya_status"] == "low_confidence"
    assert first.metadata["laya_confidence"] == 0.9
    assert second.metadata["laya_confidence"] == 0.2


# --- configuration ----------------------------------------------------------


def test_from_settings_is_disabled_by_default_and_when_blank() -> None:
    assert Settings(_env_file=None).laya_url is None
    assert LayaClient.from_settings(Settings(_env_file=None)) is None
    assert LayaClient.from_settings(Settings(_env_file=None, laya_url="")) is None


def test_from_settings_builds_client() -> None:
    client = LayaClient.from_settings(
        Settings(_env_file=None, laya_url=LAYA_URL, laya_timeout_seconds=30.0, laya_api_key="fake")
    )
    assert client is not None
    assert client.url == LAYA_URL
    assert client.timeout_seconds == 30.0
    assert "fake" not in repr(client)


@pytest.mark.parametrize("url", ["ftp://laya.test/x", "laya.test/v1", "http:///v1"])
def test_non_http_laya_url_is_rejected(url: str) -> None:
    with pytest.raises(ValueError, match="LAYA_URL"):
        Settings(_env_file=None, laya_url=url)


def test_settings_defaults_and_secret_masking() -> None:
    settings = Settings(_env_file=None, laya_api_key="super-secret-laya-key")
    assert settings.laya_timeout_seconds == 3.0
    assert settings.laya_min_confidence == 0.6
    assert "super-secret-laya-key" not in repr(settings)
    assert "super-secret-laya-key" not in str(settings.model_dump())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("laya_timeout_seconds", 0),
        ("laya_timeout_seconds", 181),
        ("laya_min_confidence", -0.1),
        ("laya_min_confidence", 1.1),
    ],
)
def test_out_of_range_settings_are_rejected(field: str, value: float) -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, **{field: value})


def _production(**overrides: Any) -> Settings:
    from pydantic import SecretStr

    return Settings(
        _env_file=None,
        environment="production",
        jwt_secret_key=SecretStr("j" * 40),
        security_token_secret=SecretStr("s" * 40),
        frontend_url="https://app.example.com",
        auth_cookie_secure=True,
        cors_origins=["https://app.example.com"],
        trusted_hosts=["api.example.com"],
        email_provider="resend",
        email_from_address="noreply@example.com",
        resend_api_key=SecretStr("configured"),
        ai_execution_enabled=False,
        **overrides,
    )


def test_production_defaults_keep_laya_off() -> None:
    assert LayaClient.from_settings(_production()) is None


@pytest.mark.parametrize(
    "url",
    [
        "https://laya.internal.example.com/v1/systemone",
        "http://127.0.0.1:8000/v1/systemone",
        "http://localhost:8000/v1/systemone",
    ],
)
def test_production_accepts_https_or_loopback(url: str) -> None:
    assert _production(laya_url=url).laya_url == url


def test_production_rejects_plain_http_to_remote_host() -> None:
    # A bearer key over plain HTTP to another host would leak in transit.
    with pytest.raises(ValueError, match="LAYA_URL must use HTTPS"):
        _production(laya_url="http://laya.internal.example.com/v1/systemone")
