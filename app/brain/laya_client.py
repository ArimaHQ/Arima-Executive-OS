"""Async client for a local ``laya-serve`` process (``POST /v1/systemone``).

Laya is optional and advisory. Every failure (unreachable, slow, HTTP error,
malformed reply, bad configuration) produces a ``LayaResult`` without
answers so callers fall back to their deterministic path instead of failing
the request. The client never raises for Laya-side problems.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from time import perf_counter
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger("arima.brain.laya")

# The English checkpoint is unreliable for Persian/Arabic-script text; pin it
# to the multilingual checkpoint (same rule as the ARYAN radar classifier).
# Latin-script input, including Finglish, uses laya-serve's automatic routing.
MULTILINGUAL_MODEL = "multilingual"
MAX_STATE_CHARS = 4000


class LayaStatus(str, Enum):
    OK = "ok"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    MALFORMED = "malformed"


@dataclass(frozen=True)
class LayaResult:
    status: LayaStatus
    answers: Mapping[str, Any] | None
    latency_ms: float


def needs_multilingual(text: str) -> bool:
    return any("؀" <= char <= "ۿ" for char in text)


class LayaClient:
    def __init__(
        self,
        url: str,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 3.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.url = url
        self._api_key = api_key
        self.timeout_seconds = timeout_seconds
        self._transport = transport

    def __repr__(self) -> str:
        return (
            f"LayaClient(url={self.url!r}, "
            f"timeout_seconds={self.timeout_seconds!r})"
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> LayaClient | None:
        if not settings.laya_url:
            return None
        api_key = (
            settings.laya_api_key.get_secret_value()
            if settings.laya_api_key
            else None
        )
        return cls(
            settings.laya_url,
            api_key=api_key,
            timeout_seconds=settings.laya_timeout_seconds,
        )

    async def predict(
        self,
        text: str,
        questions: Mapping[str, Any],
    ) -> LayaResult:
        started = perf_counter()
        try:
            # httpx timeouts apply per network phase; bound the whole call so
            # a slow-trickling server cannot hold a request past the budget.
            async with asyncio.timeout(self.timeout_seconds):
                payload = await self._post(text, questions)
        except (TimeoutError, httpx.TimeoutException):
            return self._failed(LayaStatus.TIMEOUT, started)
        except (httpx.HTTPError, httpx.InvalidURL):
            return self._failed(LayaStatus.UNAVAILABLE, started)
        except ValueError:
            # Invalid JSON or undecodable body.
            return self._failed(LayaStatus.MALFORMED, started)
        answers = payload.get("answers") if isinstance(payload, dict) else None
        if not isinstance(answers, dict):
            return self._failed(LayaStatus.MALFORMED, started)
        return LayaResult(LayaStatus.OK, answers, _elapsed_ms(started))

    async def _post(self, text: str, questions: Mapping[str, Any]) -> Any:
        body: dict[str, Any] = {
            "state": {"text": text[:MAX_STATE_CHARS]},
            "questions": dict(questions),
        }
        if needs_multilingual(text):
            body["model"] = MULTILINGUAL_MODEL
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, transport=self._transport
        ) as client:
            response = await client.post(self.url, json=body, headers=headers)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _failed(status: LayaStatus, started: float) -> LayaResult:
        latency_ms = _elapsed_ms(started)
        # Never log request text, headers or the API key.
        logger.warning(
            "laya_unavailable",
            extra={"laya_status": status.value, "latency_ms": latency_ms},
        )
        return LayaResult(status, None, latency_ms)


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)
