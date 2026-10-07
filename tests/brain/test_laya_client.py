import asyncio
import json
import logging
from typing import Any

import httpx
import pytest

from app.brain.laya_client import (
    MAX_STATE_CHARS,
    LayaClient,
    LayaResult,
    LayaStatus,
)
from tests.brain.fake_laya import fake_laya_server

URL = "http://laya.test/v1/systemone"
QUESTIONS = {"intent": {"type": "choice", "instructions": "x", "criteria": {"a": "b"}}}
FAKE_KEY = "test-laya-key-not-real"


def _mock(handler) -> LayaClient:
    return LayaClient(
        URL,
        api_key=FAKE_KEY,
        timeout_seconds=1.0,
        transport=httpx.MockTransport(handler),
    )


def _predict(client: LayaClient, text: str = "Review my portfolio") -> LayaResult:
    return asyncio.run(client.predict(text, QUESTIONS))


def test_valid_response_returns_answers() -> None:
    answers = {"intent": {"choice": "a", "confidence": 0.9}}
    result = _predict(_mock(lambda _: httpx.Response(200, json={"answers": answers})))
    assert result.status is LayaStatus.OK
    assert result.answers == answers
    assert result.latency_ms >= 0


@pytest.mark.parametrize("status_code", [400, 401, 413, 422, 500, 503])
def test_http_errors_are_unavailable(status_code: int) -> None:
    result = _predict(_mock(lambda _: httpx.Response(status_code, json={"detail": "x"})))
    assert result == LayaResult(LayaStatus.UNAVAILABLE, None, result.latency_ms)


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("refused"),
        httpx.RemoteProtocolError("dropped"),
        httpx.UnsupportedProtocol("ftp"),
    ],
)
def test_network_errors_are_unavailable(error: Exception) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise error

    assert _predict(_mock(handler)).status is LayaStatus.UNAVAILABLE


def test_httpx_timeouts_are_timeouts() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    assert _predict(_mock(handler)).status is LayaStatus.TIMEOUT


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"\xff\xfe\x00garbage",
        b"[]",
        b'"answers"',
        b"{}",
        b'{"answers": null}',
        b'{"answers": ["intent"]}',
    ],
)
def test_malformed_bodies_are_malformed(body: bytes) -> None:
    result = _predict(_mock(lambda _: httpx.Response(200, content=body)))
    assert result.status is LayaStatus.MALFORMED
    assert result.answers is None


def test_invalid_url_is_unavailable_not_a_crash() -> None:
    client = LayaClient("http://[not-a-host/v1", timeout_seconds=1.0)
    assert _predict(client).status is LayaStatus.UNAVAILABLE


def test_unrelated_programming_errors_are_not_swallowed() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise KeyError("bug in our code")

    with pytest.raises(KeyError):
        _predict(_mock(handler))


def test_request_shape_auth_and_verbatim_text() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"answers": {}})

    text = "What’s WTI vs XAU/USD, EURUSD, S&P 500 (SPX) and ＶＩＸ?"
    _predict(_mock(handler), text)
    body = json.loads(seen[0].content)
    assert seen[0].headers["Authorization"] == f"Bearer {FAKE_KEY}"
    # Laya sees the user's exact text; identifiers are never rewritten.
    assert body["state"] == {"text": text}
    assert body["questions"] == QUESTIONS
    assert "model" not in body


def test_no_authorization_header_without_key() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"answers": {}})

    client = LayaClient(URL, transport=httpx.MockTransport(handler))
    asyncio.run(client.predict("hi", QUESTIONS))
    assert "Authorization" not in seen[0].headers


@pytest.mark.parametrize(
    ("text", "pinned"),
    [
        ("برای سه ماه آینده برنامه بریز", True),
        ("قیمت WTI الان چنده؟", True),
        ("Plan next quarter", False),
        ("qeymat-e BTC chande?", False),
        ("barname-ye fasl-e ba'd ro benevis", False),
    ],
)
def test_arabic_script_is_pinned_to_multilingual(text: str, pinned: bool) -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"answers": {}})

    _predict(_mock(handler), text)
    assert ("model" in seen[0]) is pinned
    assert seen[0]["state"]["text"] == text


def test_state_is_bounded() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"answers": {}})

    _predict(_mock(handler), "x" * (MAX_STATE_CHARS + 500))
    assert len(seen[0]["state"]["text"]) == MAX_STATE_CHARS


def test_secrets_and_content_never_reach_logs_or_repr(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Migration tests run Alembic's fileConfig(), which disables loggers that
    # already exist in this process; re-enable ours so the check is real.
    monkeypatch.setattr(logging.getLogger("arima.brain.laya"), "disabled", False)

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"refused {FAKE_KEY}")

    client = _mock(handler)
    with caplog.at_level(logging.DEBUG, logger="arima.brain.laya"):
        _predict(client, "private portfolio detail 12345")
    logged = " ".join(
        f"{record.getMessage()} {record.__dict__}" for record in caplog.records
    )
    assert caplog.records
    assert FAKE_KEY not in logged
    assert "private portfolio detail" not in logged
    assert FAKE_KEY not in repr(client)


def test_real_socket_round_trip() -> None:
    with fake_laya_server() as (url, behaviour):
        behaviour.choice, behaviour.confidence = "portfolio", 0.93
        client = LayaClient(url, api_key=FAKE_KEY, timeout_seconds=5.0)
        result = asyncio.run(client.predict("How do my holdings look?", QUESTIONS))
    assert result.status is LayaStatus.OK
    assert result.answers["intent"]["choice"] == "portfolio"
    assert behaviour.requests[0]["authorization"] == f"Bearer {FAKE_KEY}"
    assert behaviour.requests[0]["body"]["state"]["text"] == "How do my holdings look?"


def test_total_timeout_bounds_a_slow_server() -> None:
    with fake_laya_server() as (url, behaviour):
        behaviour.delay_seconds = 2.0
        client = LayaClient(url, timeout_seconds=0.3)
        result = asyncio.run(client.predict("hi", QUESTIONS))
    assert result.status is LayaStatus.TIMEOUT
    assert result.latency_ms < 1500


def test_total_timeout_covers_a_trickling_body() -> None:
    # Each chunk arrives inside httpx's per-read timeout, but the whole
    # response takes longer than the configured budget.
    class Trickle(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(20):
                await asyncio.sleep(0.05)
                yield b" "
            yield b'{"answers": {}}'

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=Trickle())

    client = LayaClient(URL, timeout_seconds=0.3, transport=httpx.MockTransport(handler))
    result = asyncio.run(client.predict("hi", QUESTIONS))
    assert result.status is LayaStatus.TIMEOUT


def test_connection_refused_on_real_socket() -> None:
    with fake_laya_server() as (url, _):
        pass  # server is now closed; its port refuses connections
    # Windows retries a refused loopback SYN for ~2s before reporting it, so
    # give the refusal time to surface instead of hitting the budget.
    client = LayaClient(url, timeout_seconds=10.0)
    result = asyncio.run(client.predict("hi", QUESTIONS))
    assert result.status is LayaStatus.UNAVAILABLE
    assert result.answers is None


def test_client_recovers_after_outage() -> None:
    with fake_laya_server() as (url, behaviour):
        client = LayaClient(url, timeout_seconds=2.0)
        behaviour.status_code = 503
        assert asyncio.run(client.predict("hi", QUESTIONS)).status is LayaStatus.UNAVAILABLE
        behaviour.status_code = 200
        assert asyncio.run(client.predict("hi", QUESTIONS)).status is LayaStatus.OK
