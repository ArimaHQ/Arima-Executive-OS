# ARIMA Execution Graph

Derived from `ARIMA_SYSTEM_AUDIT.md` (2026-09-24). Status vocabulary:
`DISCOVERED | READY | RUNNING | BLOCKED | FAILED | RETRY | VERIFYING | PASSED | COMPLETED | REJECTED`.

**Rules**
- A task is `COMPLETED` only when implementation, integration, tests, and production-like verification all have evidence.
- A task is `PASSED` when its tests pass but production-like verification is still missing.
- A dependent task cannot move past `READY` while any of its dependencies is below `PASSED`.
- Owner `claude-code` means work in this repository. `human` means credentials, infrastructure, legal, or physical devices. `external-repo` means the code lives in a repository this session cannot access.

## Dependency spine

```
EPIC-01 Discovery ──► EPIC-02 Architecture
        │
        ├─► EPIC-16 Security (execution policy B2) ─────────────────────────┐
        │                                                                   │
        ├─► EPIC-04 Data (Layer 1 ingestion B1) ─► EPIC-05 Memory ─► EPIC-03 Brain ─► EPIC-11 ARIMA OS API
        │            │                               │                 │
        │            └─► EPIC-08 FIC ◄── EPIC-09 Quant (B5) ◄── EPIC-10 Risk
        │                                               │
        ├─► EPIC-07 Laya (B4) ─► EPIC-13 Jarvis API ◄─────┘ (status of all of the above)
        │
        └─► EPIC-12 Website / EPIC-14 World / PhoneCam  ── BLOCKED: external repos not accessible
                                                   EPIC-18 E2E ─► EPIC-19 Performance ─► EPIC-20 Production
```

## EPIC-01 DISCOVERY

| Task | Purpose | Owner | Deps | Acceptance | Test / evidence | Status |
|---|---|---|---|---|---|---|
| T-01.1 | Inventory all repos this account can reach | claude-code | — | Every repo classified | `ARIMA_SYSTEM_AUDIT.md` §0 | COMPLETED |
| T-01.2 | Baseline test suite on original main | claude-code | — | Real pass/fail counts | 556 passed / 4 failed | COMPLETED |
| T-01.3 | Migrations on real PostgreSQL | claude-code | — | up/down/up clean, single head | PG16 run, 82 tables | COMPLETED |
| T-01.4 | Live-server production-like E2E harness | claude-code | T-01.3 | Real HTTP + DB + SMTP, no dependency overrides | `scripts/local_e2e_verification.py`, `reports/evidence/e2e_phase*.json` | COMPLETED |

## EPIC-02 ARCHITECTURE

| Task | Purpose | Owner | Deps | Acceptance | Status |
|---|---|---|---|---|---|
| T-02.1 | Map existing components to Brain layers | claude-code | T-01.* | Audit §3 positions every component | COMPLETED |
| T-02.2 | Declare the orchestration pipeline the **single Brain entrypoint** (Middle Brain); Left/Right Brain become evidence inputs, not new brains | claude-code | T-02.1 | No second pipeline or brain class introduced | COMPLETED (architecture decision; enforced by review) |

## EPIC-REPAIR (baseline defects)

| Task | Defect | Owner | Acceptance | Evidence | Status |
|---|---|---|---|---|---|
| T-R.1 | D1 voice live-market routing regression | claude-code | 4 failing tests pass; non-live side locked by tests | `tests/tools/test_live_data_voice_tools.py`, `test_routing_planning.py` | COMPLETED |
| T-R.2 | D2 list env settings crash startup | claude-code | Comma and JSON formats both load; live server boots | `tests/test_settings_environment.py` + live boot | COMPLETED |
| T-R.3 | D2b `.env.example` fails validation | claude-code | Template loads | same test file | COMPLETED |
| T-R.4 | D3 market response hard-coded BTC | claude-code | Instrument-correct text; mismatched quote never relabelled | `test_market_voice_contract.py` + E2E gold check | COMPLETED |
| T-R.5 | D4 pre-bootstrap workspaces have no Brain access | claude-code | Backfill missing grants; revocations preserved; idempotent | `test_agent_foundation.py` + E2E early-client check | COMPLETED |
| T-R.6 | Mock background jobs (`quant_research_summary`, `growth_content_review`) routed from the planner | claude-code | QUANT intent no longer executes a mock that reports success | test | READY |
| T-R.7 | Founder data-feed catalogue is stale (claims documents and portfolio models are absent) | claude-code | Catalogue reflects the real contracts | test | READY |

## EPIC-16 SECURITY

| Task | Purpose | Owner | Deps | Acceptance | Status |
|---|---|---|---|---|---|
| T-16.1 | Canonical immutable `ExecutionPolicy` (`authority=NONE, live=false, autonomous=false, paper=true, external=DISCONNECTED`) | claude-code | — | Single source; QTrade asserts it; mutation impossible; invariant tests | READY |
| T-16.2 | Expose the policy read-only to Jarvis | claude-code | T-16.1 | Founder-only endpoint; clients get 403 | READY |
| T-16.3 | Production MFA gate evidence | human | HTTPS deploy | Founder blocked pre-MFA in production | BLOCKED (no production access) |
| T-16.4 | Tenant-isolation tests for every new API | claude-code | each new API | Cross-workspace access returns 403/404 | continuous |

## EPIC-04 DATA (Layer 1 + Middle Layer 1)

| Task | Purpose | Owner | Deps | Acceptance | Status |
|---|---|---|---|---|---|
| T-04.1 | **Knowledge ingestion API** (B1): register sources and ingest documents into the existing store | claude-code | T-16.4 | Membership + role + CSRF enforced; provenance required; credentials rejected; audited | READY |
| T-04.2 | Source reliability tier and authority metadata (migration) | claude-code | T-04.1 | `official / primary / established / unverified / user_provided`; default `unverified` | READY |
| T-04.3 | Validation pipeline: normalise, dedupe, cross-source corroboration count, conflict flag | claude-code | T-04.1 | Duplicate content is not re-chunked; corroboration recorded; frequency never becomes a truth flag | READY |
| T-04.4 | Source health (last observation, document count, freshness state, retrieval usage) | claude-code | T-04.2 | Derived from real rows only | READY |
| T-04.5 | Official macro calendar adapter (port v3 BLS/Fed/BEA feed parsing into an ingestion worker) | claude-code | T-04.1–3 | Parser unit-tested on recorded fixtures | READY |
| T-04.6 | Live fetch of official feeds | human | T-04.5 | Network policy allows the hosts; real document ingested with provenance | BLOCKED (network policy 403) |
| T-04.7 | ECB/BBC/cross-source workers | external-repo | — | — | BLOCKED (not accessible) |

## EPIC-05 MEMORY (Layer 4)

| Task | Purpose | Owner | Deps | Acceptance | Status |
|---|---|---|---|---|---|
| T-05.1 | Memory search API over the knowledge store (read-only, provenance and freshness in every result) | claude-code | T-04.1 | Workspace-scoped; stale and provenance-less results excluded | READY |
| T-05.2 | Reliability- and corroboration-weighted ranking | claude-code | T-04.2, T-04.3 | Ranking only reorders; it never admits invalid evidence | READY |
| T-05.3 | E2E: ingested source reaches a Brain answer as cited evidence | claude-code | T-04.1, T-05.1 | Voice answer contains `[evidence:…]` from the ingested document | READY |
| T-05.4 | Semantic embeddings (pgvector) | claude-code + human | embedding provider credential | Extension installed; hybrid retrieval | BLOCKED (no embedding provider enabled; pgvector not installed) |
| T-05.5 | Hot/warm/cold tiers and long-document compression | claude-code | T-05.4 | — | DISCOVERED |

## EPIC-03 BRAIN

| Task | Purpose | Owner | Deps | Acceptance | Status |
|---|---|---|---|---|---|
| T-03.1 | Right-brain guard: context/preference evidence is typed and can never feed financial computation | claude-code | T-05.1 | Tests prove preference memory is excluded from financial inputs | READY |
| T-03.2 | Layer 3 synthesis (hypothesis → evidence → confidence) | claude-code | T-04.*, T-05.*, T-09.* | Needs real data first | BLOCKED (on data) |
| T-03.3 | Ollama/Qwen and Anthropic provider adapters | claude-code | reachable runtime | Real completion round-trip | BLOCKED (no runtime or credential reachable) |

## EPIC-07 LAYA

| Task | Purpose | Owner | Deps | Acceptance | Status |
|---|---|---|---|---|---|
| T-07.1 | Persistent task graph: TASK_ID, purpose, owner, deps, inputs/outputs, acceptance, tests, status, evidence, blockers | claude-code | T-16.1 | Migration + service | READY |
| T-07.2 | Dependency enforcement: a task cannot pass/complete before its dependencies | claude-code | T-07.1 | Invariant tests | READY |
| T-07.3 | Failure classification (transient / data / code / dependency / permission / infrastructure / architectural) with retry versus escalate | claude-code | T-07.1 | Tests | READY |
| T-07.4 | Founder-only API (Jarvis → Laya) | claude-code | T-07.1, T-16.2 | Clients get 403; audited | READY |

## EPIC-13 JARVIS (backend)

| Task | Purpose | Owner | Deps | Acceptance | Status |
|---|---|---|---|---|---|
| T-13.1 | Brain status: agents, grants, providers, sources, knowledge coverage, execution policy, Laya summary | claude-code | T-04.4, T-07.4, T-16.2 | Founder-only; real rows only | READY |
| T-13.2 | Jarvis UI | external-repo | T-13.1 | — | BLOCKED (not accessible) |

## EPIC-09 QUANT / EPIC-10 RISK / EPIC-08 FIC

| Task | Purpose | Owner | Deps | Acceptance | Status |
|---|---|---|---|---|---|
| T-09.1 | Port Monte Carlo (bootstrap resampling, drawdown, ruin, percentiles) as a pure, seeded, tenant-agnostic function | claude-code | — | Parity with v3 on the same seed and input | READY |
| T-09.2 | Scenario / stress API over caller-supplied return series with provenance | claude-code | T-09.1 | Research-only; no execution coupling | READY |
| T-09.3 | Backtest engine port | claude-code | T-04.6 (historical data) | — | BLOCKED (no verified historical data) |
| T-10.1 | Authoritative daily-loss/exposure source | human + claude-code | broker/ledger contract | — | BLOCKED |
| T-08.1 | FIC (intrinsic value, regime, bubble, cross-asset) | claude-code | T-04.6, T-09.* | — | BLOCKED (on data) |

## EPIC-11 ARIMA OS / EPIC-12 WEBSITE / EPIC-14 WORLD / EPIC-15 FINANCIAL SERVICES

| Task | Owner | Status |
|---|---|---|
| T-11.1 Backend APIs for OS (existing + knowledge/memory) | claude-code | partial; APIs verified by E2E |
| T-11.2 OS client UI | external-repo | BLOCKED (not accessible) |
| T-12.1 Website | external-repo | BLOCKED (only a static early-access page is accessible) |
| T-14.* World (visual fidelity, 12–20 user proof) | external-repo | BLOCKED (not accessible) |
| T-15.1 Financial services over Brain APIs | claude-code | DISCOVERED (depends on EPIC-04/05/09) |
| PhoneCam | external-repo + devices | BLOCKED |

## EPIC-17 OBSERVABILITY / EPIC-18 E2E / EPIC-19 PERFORMANCE / EPIC-20 PRODUCTION

| Task | Owner | Status |
|---|---|---|
| T-17.1 Correlation IDs, request logs, telemetry, audit (existing) | claude-code | PASSED (verified in logs) |
| T-18.1 Local production-like E2E (auth, MFA, founder, isolation, market, Brain, refresh replay) | claude-code | COMPLETED (56/56) |
| T-18.2 E2E for new knowledge → Brain path | claude-code | READY |
| T-19.1 API latency/concurrency baseline on local PostgreSQL | claude-code | READY |
| T-20.1 Production deploy verification | human | BLOCKED (no production access or credentials) |

## Execution order for this session

T-R.* → **T-16.1/16.2** → **T-04.1–04.4** → **T-05.1–05.3** → **T-03.1** → **T-07.1–07.4** → **T-13.1** → T-09.1/09.2 → T-R.6/R.7 → T-18.2/T-19.1 → final report.
Each item is updated here with evidence as it lands.
