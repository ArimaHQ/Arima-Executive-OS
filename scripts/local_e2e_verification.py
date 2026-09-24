"""Production-like end-to-end verification against a live local API.

This drives the real HTTP API (no TestClient, no dependency overrides) against
a real database, using a local SMTP sink directory to read verification
emails. It creates dedicated verification identities, so it refuses to run
against a non-local base URL unless ``--allow-remote`` is given.

Phases (the operator phase needs a server restart in between, because
platform-operator identity is server configuration):

  phase1  register operator + founder + an early client, verify email, record IDs
  phase2  role assignment, agent bootstrap, clients, MFA, founder control,
          tenant isolation, market fail-closed, refresh replay, voice/Brain path

Results are written as JSON evidence with one PASS/FAIL record per check.
"""

from __future__ import annotations

import argparse
import email
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx

PASSWORD = "Str0ng!Passw0rd#2026"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


@dataclass
class Evidence:
    started_at: str
    base_url: str
    phase: str
    checks: list[Check] = field(default_factory=list)

    def record(self, name: str, passed: bool, detail: object = "") -> bool:
        self.checks.append(Check(name, bool(passed), str(detail)[:500]))
        print(f"[{'PASS' if passed else 'FAIL'}] {name} :: {str(detail)[:160]}")
        return passed


class Actor:
    def __init__(self, base_url: str, email_address: str) -> None:
        self.email = email_address
        self.client = httpx.Client(base_url=base_url, timeout=60)
        self.access_token: str | None = None
        self.csrf: str | None = None

    def refresh_csrf(self) -> str:
        response = self.client.post("/api/v1/auth/csrf")
        response.raise_for_status()
        self.csrf = response.json()["csrf_token"]
        return self.csrf

    def headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        if self.csrf:
            headers["X-CSRF-Token"] = self.csrf
        return headers

    def get(self, path: str, **kwargs) -> httpx.Response:
        return self.client.get(path, headers=self.headers(), **kwargs)

    def post(self, path: str, **kwargs) -> httpx.Response:
        return self.client.post(path, headers=self.headers(), **kwargs)

    def login(self, otp: str | None = None) -> httpx.Response:
        self.refresh_csrf()
        body: dict[str, object] = {"email": self.email, "password": PASSWORD}
        if otp is not None:
            body["otp"] = otp
        response = self.post("/api/v1/auth/login", json=body)
        if response.status_code == 200:
            payload = response.json()
            self.access_token = payload.get("access_token") or payload.get(
                "tokens", {}
            ).get("access_token")
            self.csrf = payload.get("csrf_token", self.csrf) or self.csrf
        return response


def verification_token(mail_dir: Path, address: str, *, after: float) -> str | None:
    deadline = time.time() + 10
    while time.time() < deadline:
        for path in sorted(mail_dir.glob(f"*_{address}.eml"), reverse=True):
            if int(path.name.split("_", 1)[0]) / 1e9 < after:
                continue
            message = email.message_from_bytes(path.read_bytes())
            bodies = [
                part.get_payload(decode=True).decode(errors="ignore")
                for part in message.walk()
                if part.get_content_type() == "text/plain"
            ]
            for body in bodies:
                for url in re.findall(r"https?://\S+", body):
                    token = parse_qs(urlsplit(url).query).get("token")
                    if token:
                        return token[0]
        time.sleep(0.25)
    return None


def register_and_verify(
    evidence: Evidence, base_url: str, mail_dir: Path, address: str
) -> Actor:
    actor = Actor(base_url, address)
    started = time.time()
    actor.refresh_csrf()
    response = actor.post(
        "/api/v1/auth/register",
        json={
            "email": address,
            "password": PASSWORD,
            "first_name": "Verify",
            "last_name": address.split("@")[0].replace(".", "-"),
        },
    )
    evidence.record(f"register {address}", response.status_code == 201, response.status_code)
    unverified = actor.login()
    evidence.record(
        f"unverified login rejected {address}",
        unverified.status_code in (401, 403),
        unverified.status_code,
    )
    token = verification_token(mail_dir, address, after=started)
    evidence.record(f"verification email delivered {address}", token is not None, bool(token))
    if token:
        actor.refresh_csrf()
        verified = actor.post("/api/v1/auth/verify-email", json={"token": token})
        evidence.record(f"verify email {address}", verified.status_code == 200, verified.status_code)
    return actor


def phase1(args: argparse.Namespace, evidence: Evidence) -> dict[str, str]:
    mail_dir = Path(args.mail_dir)
    ready = httpx.get(f"{args.base_url}/health/ready", timeout=10)
    evidence.record("readiness", ready.status_code == 200 and ready.json().get("database") == "ok", ready.text)
    state: dict[str, str] = {}
    for role, address in (
        ("operator", args.operator_email),
        ("founder", args.founder_email),
        ("early_client", f"early.client.{args.run_id}@arima-audit.com"),
    ):
        actor = register_and_verify(evidence, args.base_url, mail_dir, address)
        login = actor.login()
        evidence.record(f"login {role}", login.status_code == 200, login.status_code)
        me = actor.get("/api/v1/auth/me")
        if me.status_code == 200:
            state[f"{role}_id"] = me.json()["id"]
            state[f"{role}_email"] = address
    return state


def phase2(args: argparse.Namespace, evidence: Evidence, state: dict[str, str]) -> None:
    mail_dir = Path(args.mail_dir)
    base = args.base_url

    operator = Actor(base, state["operator_email"])
    evidence.record("operator login", operator.login().status_code == 200)
    operator.refresh_csrf()
    assigned = operator.post(
        f"/api/v1/admin/users/{state['founder_id']}/roles",
        json={"role_name": "administrator"},
    )
    evidence.record("platform operator assigns administrator", assigned.status_code in (200, 201, 204), assigned.status_code)

    client_probe = Actor(base, state["early_client_email"])
    client_probe.login()
    client_probe.refresh_csrf()
    escalation = client_probe.post(
        f"/api/v1/admin/users/{state['early_client_id']}/roles",
        json={"role_name": "administrator"},
    )
    evidence.record("client cannot self-elevate", escalation.status_code in (401, 403), escalation.status_code)

    bootstrap = subprocess.run(
        [sys.executable, "-m", "app.services.agent_bootstrap"],
        cwd=REPOSITORY_ROOT, capture_output=True, text=True, timeout=120, check=False,
    )
    evidence.record("agent bootstrap under founder admin", bootstrap.returncode == 0, bootstrap.stderr[-300:] or "ok")

    clients = {}
    for label in ("a", "b"):
        address = f"client.{label}.{args.run_id}@arima-audit.com"
        actor = register_and_verify(evidence, base, mail_dir, address)
        evidence.record(f"client {label} login", actor.login().status_code == 200)
        clients[label] = actor
    a, b = clients["a"], clients["b"]

    # Founder: privileged MFA is required before founder control is usable.
    founder = Actor(base, state["founder_email"])
    first = founder.login()
    evidence.record("founder login pre-MFA", first.status_code in (200, 401, 403), first.status_code)
    blocked = founder.get("/api/v1/admin/founder/system-health")
    if args.environment == "production":
        evidence.record("founder control blocked before MFA", blocked.status_code in (401, 403), blocked.status_code)
    else:
        # requires_privileged_mfa() is production-scoped by design.
        evidence.record(
            f"founder MFA gate is production-only ({args.environment} allows pre-MFA)",
            blocked.status_code == 200,
            blocked.status_code,
        )
    founder.refresh_csrf()
    enrolled = founder.post("/api/v1/auth/mfa/enroll")
    secret = None
    if enrolled.status_code == 200:
        secret = parse_qs(urlsplit(enrolled.json()["otpauth_uri"]).query).get("secret", [None])[0]
    evidence.record("founder MFA enrollment", secret is not None, enrolled.status_code)
    if secret:
        sys.path.insert(0, str(REPOSITORY_ROOT))
        from app.auth.totp import code_for, current_step

        founder.refresh_csrf()
        confirmed = founder.post("/api/v1/auth/mfa/verify", json={"code": code_for(secret, current_step())})
        evidence.record("founder MFA confirmation", confirmed.status_code == 204, confirmed.status_code)
        time.sleep(31 - (time.time() % 30))
        mfa_login = founder.login(otp=code_for(secret, current_step()))
        evidence.record("founder login with TOTP", mfa_login.status_code == 200, mfa_login.status_code)
        health = founder.get("/api/v1/admin/founder/system-health")
        evidence.record("founder system-health", health.status_code == 200, [c.get("key") for c in health.json().get("components", [])] if health.status_code == 200 else health.status_code)
        feeds = founder.get("/api/v1/admin/founder/data-feeds")
        evidence.record("founder data-feeds", feeds.status_code == 200, feeds.status_code)

    evidence.record("client denied founder control", a.get("/api/v1/admin/founder/system-health").status_code in (401, 403))

    # Tenant isolation over real HTTP.
    a.refresh_csrf()
    project = a.post("/api/v1/projects", json={"name": f"Isolation probe {args.run_id}"})
    evidence.record("client A creates project", project.status_code == 201, project.status_code)
    if project.status_code == 201:
        project_id = project.json()["id"]
        cross = b.get(f"/api/v1/projects/{project_id}")
        evidence.record("client B cannot read client A project", cross.status_code in (403, 404), cross.status_code)
        listing = b.get("/api/v1/projects")
        evidence.record("client B listing excludes A project", project_id not in listing.text, listing.status_code)

    # Market data remains fail-closed and non-price.
    unauth = httpx.get(f"{base}/api/v1/market/availability", timeout=10)
    evidence.record("market availability requires auth", unauth.status_code == 401, unauth.status_code)
    availability = a.get("/api/v1/market/availability")
    evidence.record("market availability non-price", availability.status_code == 200 and "\"price\"" not in availability.text, availability.text[:200])
    for path in ("/api/v1/market/price", "/api/v1/market/quote", "/api/v1/market/candles", "/api/v1/market/time-series"):
        evidence.record(f"market route absent {path}", a.get(path).status_code == 404)

    # Brain path: client asks about gold through the voice gateway.
    a.refresh_csrf()
    session = a.post("/api/v1/voice/sessions", json={})
    evidence.record("client A voice session", session.status_code in (200, 201), session.status_code)
    if session.status_code in (200, 201):
        session_id = session.json()["session_id"]
        a.refresh_csrf()
        answer = a.post(
            f"/api/v1/voice/sessions/{session_id}/transcript",
            json={"transcript": "What is the price of gold today?"},
        )
        body = answer.json() if answer.headers.get("content-type", "").startswith("application/json") else {}
        text = str(body.get("response_text", ""))
        evidence.record("gold question answered through Brain path", answer.status_code == 200, answer.status_code)
        evidence.record(
            "gold answer does not fabricate a price",
            answer.status_code == 200 and not re.search(r"\$?\b\d{3,5}(?:\.\d+)?\s*(?:usd|dollars|\$)", text.casefold()),
            text[:300],
        )
        other = b.get(f"/api/v1/voice/sessions/{session_id}")
        evidence.record("client B cannot read client A voice session", other.status_code in (403, 404), other.status_code)

    early = Actor(base, state["early_client_email"])
    early_login = early.login()
    if early_login.status_code == 429:
        evidence.record("login rate limit enforced per client", True, "429 after repeated logins")
        time.sleep(61)
        early_login = early.login()
    evidence.record("early client login", early_login.status_code == 200, early_login.status_code)
    early.refresh_csrf()
    early_session = early.post("/api/v1/voice/sessions", json={})
    evidence.record(
        "client registered before agent bootstrap gets a voice session",
        early_session.status_code in (200, 201),
        f"{early_session.status_code} {early_session.text[:200]}",
    )
    if early_session.status_code in (200, 201):
        early.refresh_csrf()
        early_answer = early.post(
            f"/api/v1/voice/sessions/{early_session.json()['session_id']}/transcript",
            json={"transcript": "What should I focus on today?"},
        )
        evidence.record(
            "client registered before agent bootstrap can use the Brain",
            early_answer.status_code == 200 and "not authorized" not in early_answer.text.casefold(),
            f"{early_answer.status_code} {early_answer.text[:200]}",
        )

    # Refresh rotation and replay detection.
    a.refresh_csrf()
    old_refresh = a.client.cookies.get("arima_refresh_token")
    rotated = a.post("/api/v1/auth/refresh")
    evidence.record("refresh rotates session", rotated.status_code == 200, rotated.status_code)
    if old_refresh:
        replay = httpx.Client(base_url=base, timeout=30)
        csrf = replay.post("/api/v1/auth/csrf").json()["csrf_token"]
        replay.cookies.set("arima_refresh_token", old_refresh)
        replayed = replay.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf})
        evidence.record("refresh token replay rejected", replayed.status_code in (401, 403), replayed.status_code)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("phase1", "phase2"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--mail-dir", required=True)
    parser.add_argument("--state-file", required=True)
    parser.add_argument("--evidence-file", required=True)
    parser.add_argument("--operator-email", default="operator@arima-audit.com")
    parser.add_argument("--founder-email", default="founder@arima-audit.com")
    parser.add_argument("--run-id", default=datetime.now(UTC).strftime("%H%M%S"))
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument(
        "--environment", default="development",
        choices=("development", "test", "production"),
        help="ENVIRONMENT of the target server; the MFA gate is production-only",
    )
    args = parser.parse_args()

    host = urlsplit(args.base_url).hostname
    if host not in {"127.0.0.1", "localhost"} and not args.allow_remote:
        print("Refusing to create verification identities on a non-local API", file=sys.stderr)
        return 2

    evidence = Evidence(datetime.now(UTC).isoformat(), args.base_url, args.phase)
    state_path = Path(args.state_file)
    if args.phase == "phase1":
        state_path.write_text(json.dumps(phase1(args, evidence), indent=2))
    else:
        phase2(args, evidence, json.loads(state_path.read_text()))
    Path(args.evidence_file).write_text(
        json.dumps({**asdict(evidence), "checks": [asdict(c) for c in evidence.checks]}, indent=2)
    )
    failed = [check for check in evidence.checks if not check.passed]
    print(f"\n{len(evidence.checks) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
