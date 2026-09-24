"""Concurrent multi-user verification against a live local API.

Registers N real users (each behind its own forwarded client IP, as in a
proxied deployment where the server trusts the proxy), then runs them
concurrently through authenticated reads, knowledge ingestion/search, and a
Brain (voice) request. It measures latency per operation and proves that no
user can see another user's knowledge under concurrent load.

Requires the server to trust the local proxy peer (TRUSTED_PROXY_IPS=127.0.0.1)
and an SMTP sink directory for verification emails. Local targets only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_e2e_verification import PASSWORD, verification_token


class User:
    def __init__(self, base_url: str, index: int, run_id: str) -> None:
        self.index = index
        self.email = f"load.{run_id}.{index}@arima-audit.com"
        self.ip = f"198.18.{index // 250}.{index % 250 + 1}"
        self.marker = f"marker{run_id}u{index:03d}end"
        self.client = httpx.AsyncClient(base_url=base_url, timeout=60, headers={"X-Forwarded-For": self.ip})
        self.token: str | None = None
        self.workspace_id: str | None = None

    async def csrf(self) -> dict[str, str]:
        response = await self.client.post("/api/v1/auth/csrf")
        return {"X-CSRF-Token": response.json()["csrf_token"]}

    def auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


async def timed(latencies: dict[str, list[float]], errors: dict[str, int], name: str, call):
    started = time.perf_counter()
    try:
        response = await call()
    except httpx.HTTPError:
        errors[name] += 1
        return None
    latencies[name].append((time.perf_counter() - started) * 1000)
    if response.status_code >= 400:
        errors[name] += 1
    return response


async def onboard(user: User, mail_dir: Path) -> bool:
    started = time.time()
    registered = await user.client.post(
        "/api/v1/auth/register",
        json={"email": user.email, "password": PASSWORD, "first_name": "Load", "last_name": str(user.index)},
        headers=await user.csrf(),
    )
    if registered.status_code != 201:
        return False
    token = await asyncio.to_thread(verification_token, mail_dir, user.email, after=started)
    if token is None:
        return False
    verified = await user.client.post("/api/v1/auth/verify-email", json={"token": token}, headers=await user.csrf())
    login = await user.client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}, headers=await user.csrf()
    )
    if verified.status_code != 200 or login.status_code != 200:
        return False
    user.token = login.json()["access_token"]
    user.workspace_id = (await user.client.get("/api/v1/auth/me", headers=user.auth())).json()["workspace"]["id"]
    return True


async def session(user: User, others: list[User], iterations: int, latencies, errors, leaks: list[str]) -> None:
    ws = f"/api/v1/knowledge/workspaces/{user.workspace_id}"
    source = await timed(latencies, errors, "knowledge.register_source", lambda: _post(user, f"{ws}/sources", {
        "source_type": "note", "external_id": user.marker, "name": f"Notes {user.index}",
    }))
    if source is not None and source.status_code == 201:
        await timed(latencies, errors, "knowledge.ingest", lambda: _post(user, f"{ws}/sources/{source.json()['id']}/documents", {
            "external_id": "n1", "title": "Private note",
            "content": f"{user.marker} private liquidity plan for user {user.index}",
            "source_observed_at": datetime.now(UTC).isoformat(), "provenance": {"source": "load-test"},
        }))
    for _ in range(iterations):
        await timed(latencies, errors, "auth.me", lambda: user.client.get("/api/v1/auth/me", headers=user.auth()))
        await timed(latencies, errors, "dashboard.summary", lambda: user.client.get("/api/v1/dashboard/summary", headers=user.auth()))
        await timed(latencies, errors, "market.availability", lambda: user.client.get("/api/v1/market/availability", headers=user.auth()))
        own = await timed(latencies, errors, "knowledge.search", lambda: user.client.get(f"{ws}/search", params={"q": user.marker}, headers=user.auth()))
        if own is not None and own.status_code == 200 and user.marker not in own.text:
            leaks.append(f"user {user.index} could not find own knowledge")
        for other in others[:2]:
            if other.marker in (own.text if own is not None else ""):
                leaks.append(f"user {user.index} saw user {other.index} content")
    voice = await timed(latencies, errors, "voice.session", lambda: _post(user, "/api/v1/voice/sessions", {}))
    if voice is not None and voice.status_code == 201:
        await timed(latencies, errors, "voice.brain_turn", lambda: _post(
            user, f"/api/v1/voice/sessions/{voice.json()['session_id']}/transcript",
            {"transcript": f"What is in my private liquidity plan {user.marker}?"},
        ))
    for other in others[:3]:
        foreign = await user.client.get(
            f"/api/v1/knowledge/workspaces/{other.workspace_id}/search",
            params={"q": other.marker}, headers=user.auth(),
        )
        if foreign.status_code != 403 or other.marker in foreign.text:
            leaks.append(f"user {user.index} reached user {other.index} workspace ({foreign.status_code})")


async def _post(user: User, path: str, payload: dict) -> httpx.Response:
    return await user.client.post(path, json=payload, headers={**user.auth(), **await user.csrf()})


def summarize(latencies: dict[str, list[float]]) -> dict[str, dict[str, float]]:
    report = {}
    for name, values in sorted(latencies.items()):
        ordered = sorted(values)
        report[name] = {
            "count": len(ordered),
            "p50_ms": round(statistics.median(ordered), 1),
            "p95_ms": round(ordered[max(0, int(len(ordered) * 0.95) - 1)], 1),
            "max_ms": round(ordered[-1], 1),
        }
    return report


async def main_async(args: argparse.Namespace) -> int:
    run_id = datetime.now(UTC).strftime("%H%M%S")
    users = [User(args.base_url, index, run_id) for index in range(args.users)]
    onboard_started = time.perf_counter()
    onboarded = await asyncio.gather(*(onboard(user, Path(args.mail_dir)) for user in users))
    onboard_seconds = time.perf_counter() - onboard_started
    ready = [user for user, ok in zip(users, onboarded, strict=True) if ok]
    latencies: dict[str, list[float]] = defaultdict(list)
    errors: dict[str, int] = defaultdict(int)
    leaks: list[str] = []
    load_started = time.perf_counter()
    await asyncio.gather(*(
        session(user, [other for other in ready if other is not user], args.iterations, latencies, errors, leaks)
        for user in ready
    ))
    load_seconds = time.perf_counter() - load_started
    for user in users:
        await user.client.aclose()
    requests = sum(len(values) for values in latencies.values())
    result = {
        "generated_at": datetime.now(UTC).isoformat(),
        "base_url": args.base_url,
        "users_requested": args.users,
        "users_authenticated": len(ready),
        "onboarding_seconds": round(onboard_seconds, 2),
        "load_seconds": round(load_seconds, 2),
        "requests": requests,
        "throughput_rps": round(requests / load_seconds, 1) if load_seconds else 0,
        "errors": dict(errors),
        "isolation_violations": leaks,
        "latency": summarize(latencies),
        "environment": "local uvicorn (1 worker) + PostgreSQL 16 on the same host; mock LLM provider",
    }
    Path(args.evidence_file).write_text(json.dumps(result, indent=2))
    print(json.dumps({k: result[k] for k in ("users_authenticated", "requests", "throughput_rps", "errors", "isolation_violations")}, indent=2))
    for name, values in result["latency"].items():
        print(f"{name:28} n={values['count']:4} p50={values['p50_ms']:7}ms p95={values['p95_ms']:7}ms max={values['max_ms']:7}ms")
    ok = len(ready) == args.users and not leaks and not any(errors.values())
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--mail-dir", required=True)
    parser.add_argument("--evidence-file", required=True)
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=5)
    args = parser.parse_args()
    if urlsplit(args.base_url).hostname not in {"127.0.0.1", "localhost"}:
        print("Refusing to create load identities on a non-local API", file=sys.stderr)
        return 2
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
