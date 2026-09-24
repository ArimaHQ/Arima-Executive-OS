# ARIMA System Audit

**Audit date:** 2026-09-24
**Audited revision:** `79a21bd` (main), branch `claude/vibrant-carson-6rx6on`
**Method:** direct inspection plus execution. Every status below comes from code read in this session, tests run in this session, or a live server exercised in this session. Nothing is copied from earlier reports. Where earlier claims could not be checked, this audit says so.

## 0. Scope: what exists and where

The prompt describes one ARIMA ecosystem: Brain, Laya, Jarvis, ARIMA OS, Website, World, PhoneCam, Finance Engine, FIC, 175 agents, and ECB/BBC/cross-source workers. Only part of that is reachable from this environment.

| Repository | Access | What it actually is | Last commit |
|---|---|---|---|
| `ArimaHQ/Arima-Executive-OS` (this repo) | read/write | FastAPI + SQLAlchemy backend: auth, tenancy, agents, orchestration, voice, market gateway, quant contracts, ledger, founder control. ~46k Python LOC, 206 endpoints, 82 tables. | 2026-08-26 |
| `ArimaHQ/-Arima-Finance-Engine-v3` (private) | read | Script-style trading-research engine: 7-phase strategy pipeline, backtest, Monte Carlo, walk-forward, official US macro calendar (BLS/Fed/BEA/Census/DOL RSS), Telegram alerts. File-based state (`data/*.json`), pandas/yfinance. ~18k LOC. | 2026-07-17 |
| `ArimaHQ/Arima-Finance-Engine` (public) | read | Public "architecture demo" of the engine with synthetic inputs. States it is non-trading. | 2026-07-18 |
| `arima7576/arima-early-access` | read | One static `index.html` early-access page. Its form posts to a Google Apps Script, not to this backend. | 2026-08-11 |
| `arima7576/Arima-Executive-OS` | read | Older snapshot of this backend (2026-07-28). Every file in it is present here. | 2026-07-28 |

**Not found in any repository this account can reach:** ARIMA World, PhoneCam, the "Brain local runtime" (175 declarative agents; ECB, BBC, cross-source and data-quality workers; Ollama/Qwen runtime), the ARIMA OS frontend, the Jarvis UI, the cinematic website, and the "World Showcase". The docs here say the frontend lives in a separate repo ("Frontend source is not part of this backend repository", `docs/production-readiness.md`). These systems are marked **[UNKNOWN — NOT ACCESSIBLE]**. They were not audited, and nothing below claims anything about them.

## 1. Baseline evidence (captured this session)

| Check | Command | Result |
|---|---|---|
| Unit/integration suite, original `main` | `python -m pytest -q` | **556 passed, 4 failed** (all in `tests/tools/test_live_data_voice_tools.py`) |
| Alembic heads | `python -m alembic heads` | single head `20260824_0026` |
| Migrations on **real PostgreSQL 16** | `alembic upgrade head` → `downgrade base` → `upgrade head` | clean both ways, 82 tables. The earlier audit had only static evidence for this. |
| Live server boot, documented `.env` format | `uvicorn app.main:app` with `TRUSTED_HOSTS=localhost,127.0.0.1` | **crashed on startup** (`SettingsError`). See defect D2. |
| Live E2E over real HTTP + PostgreSQL + SMTP | `scripts/local_e2e_verification.py` | first run found defects D3, D4 and D5. After repair: phase 1 **16/16**, phase 2 **40/40** (`reports/evidence/`) |
| Outbound data sources | `curl` to bls.gov, federalreserve.gov, ecb.europa.eu, bbc.co.uk, api.twelvedata.com, bea.gov | **all blocked by this environment's network policy (HTTP 403 at the proxy).** This is an infrastructure blocker, not a code defect. |

## 2. Defects found and repaired in this session

| ID | Severity | Defect | Root cause | Repair | Verification |
|---|---|---|---|---|---|
| D1 | High (regression) | 4 failing tests. "What's WTI doing?", "What's FTSE 100?", "What is Bitcoin's price?" and "gold price" no longer routed to the market tool. | Commit `3ed7e87` narrowed `_is_live_market_request` to a fixed phrase list. | Restored "doing", word-level "price" and Persian "قیمت" as live markers. Contracted "what's &lt;instrument&gt;?" treated as a level request. Added "explain", "why" and "چرا" as conceptual guards. | 4 failures now pass. New test locks the non-live side ("What is Bitcoin?", "Why did…", Persian "why"). |
| D2 | High (deploy) | API cannot start with the documented comma-separated `CORS_ORIGINS`, `TRUSTED_HOSTS`, `TRUSTED_PROXY_IPS` or `PLATFORM_OPERATOR_USER_IDS`. A single bare value also fails. | pydantic-settings JSON-decodes `list[...]` env values before the existing comma validator runs. Only `FOUNDER_CONTROL_EMAILS` had `NoDecode`. | `NoDecode` on all four. The validator now accepts comma **or** JSON-array input, so an existing JSON-configured deployment keeps working. | `tests/test_settings_environment.py` (fails before the fix, passes after). Live server boots with the comma format. |
| D2b | Medium (deploy) | Copying `.env.example` to `.env` failed validation. | Blank `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `SMTP_FROM_EMAIL` and `SMTP_FROM_NAME` violate field constraints. | Blank optional lines commented out in the template. Production semantics unchanged. | `test_env_example_file_loads_without_settings_errors` |
| D3 | **High (data integrity)** | Asking about gold answered "A verified **BTC** price is currently unavailable". Once any verified non-BTC quote arrived, it would have been published **labelled as the BTC/USD price**. | `market_response` hard-coded "BTC/USD" for every instrument. | Response now names the planned instrument. A quote whose `instrument` differs from the one requested is treated as unavailable, never relabelled. | 7 new contract tests. E2E: "A verified XAU/USD price is currently unavailable." |
| D4 | High (availability) | Every account registered before the agent bootstrap had **no path to the Brain** ("Voice AI authorization denied"). This included the operator and founder accounts. | Registration grants the default agent only if it already exists. The founder grant endpoint requires the founder to own the target workspace. Clients have no grant endpoint. | `bootstrap_agent_platform` backfills the default-agent grant into workspaces that have **no** grant row, the same policy registration applies. Revoked grants are never re-enabled. | New test: backfill, revocation preserved, idempotent. E2E: pre-bootstrap client gets session 201 and a Brain answer 200. |

The prior audit's highest-severity item was **re-checked and is resolved**. `PortfolioRiskProvider.snapshot` no longer substitutes zero for missing daily-loss, strategy-exposure or valuation inputs. It raises `RiskInputUnavailableError`/`ValuationUnavailableError` (`app/services/risk_contract.py:241-259`).

## 3. Component inventory (this repository)

Classifications: **[KEEP] [INTEGRATE] [EXTEND] [REPAIR] [REFACTOR] [REPLACE] [REMOVE] [UNKNOWN]**

### 3.1 Platform, security, tenancy

| Component | Location | Current state / evidence | Tests | Security | Class | Required action |
|---|---|---|---|---|---|---|
| Auth (register, verify, login, refresh rotation, lockout, rate limits, CSRF, sessions) | `app/auth/`, `routes/auth.py` | Works over real HTTP. Unverified login rejected (403). Refresh replay rejected (401). Login rate limit returned 429 under load. | 39 unit tests + E2E | Argon2, JWT with issuer and audience, double-submit CSRF, fail-closed email | KEEP | none |
| Privileged MFA (TOTP, AES-GCM secret at rest) | `app/auth/totp.py`, `auth/service.py` | Enrol, confirm and TOTP login work end to end. **Enforced only when `ENVIRONMENT=production`** (`requires_privileged_mfa`). | `tests/auth/test_mfa.py` + E2E | By design | KEEP | Production gate needs HTTPS deployment evidence |
| RBAC + platform operator + Founder allowlist | `app/services/permissions.py`, `auth/dependencies.py` | Operator assigns the administrator role. A client trying to self-elevate gets 403. A client calling founder control gets 403. | `test_rbac`, `test_founder_control`, E2E | Allowlist empty means deny-all | KEEP | none |
| Tenancy (Tenant → Workspace → Membership) | `database/models/workspace.py` | Cross-tenant reads of projects and voice sessions return 404/403 over HTTP | `test_tenant_isolation_adversarial` + E2E | Enforced in services | KEEP | Extend isolation tests to each new API |
| `WorkspaceAgentGrant` | `app/intelligence/access.py` | Works. Gap D4 repaired. | + new test | Explicit grant required | KEEP (repaired) | none |
| Audit log | `services/audit.py` | `record_audit` is called on every mutating path inspected | indirect | yes | KEEP | none |
| Settings / config | `app/core/config.py` | D2 and D2b repaired. Production validators are strict: HTTPS origins, no mock provider, secure cookies. | + 4 new tests | fail-closed | KEEP (repaired) | none |

### 3.2 Brain candidates: orchestration, agents, providers, memory

| Component | Location | Current state / evidence | Architecture position | Class | Required action |
|---|---|---|---|---|---|
| Orchestration pipeline (intent → agent/provider/model routing → memory → planner → approvals → executor → prompt → validation → cost → telemetry → audit) | `app/orchestration/` (3.1k LOC) | Works end to end over HTTP through the voice gateway (E2E). **This is the de facto central Brain / Middle Brain.** It is request-scoped, not a long-running cognition loop. | Middle Brain (decision/action core) | KEEP / EXTEND | Name it as the single Brain entrypoint. Add Left/Right-brain context as evidence inputs, not as new brains. |
| Intent engine + planner | `orchestration/router.py`, `planner.py` | Keyword and marker based, closed instrument catalogue. D1 repaired. | Middle Brain routing | KEEP (repaired) | none |
| Response validator + provider prompt | `response_validation.py`, `provider_prompt.py` | Evidence-ID citation contract. Instructions and evidence treated as untrusted. Never invents state. | Output safety | KEEP | none |
| Deterministic market response | `market_response.py` | D3 repaired | Output safety | KEEP (repaired) | none |
| Agent platform (definitions, conversations, messages, runs, tool executions, approvals, memory) | `services/agent.py`, `models/agent.py` | Persistent and audited. **Only one agent is seeded** (`executive-assistant`). The "175 declarative agents" do not exist here. | Brain components | KEEP / EXTEND | Add specialist agents only where a capability exists behind them. Do not create empty names. |
| Providers | `app/providers/` | Real adapters: Gemini, OpenAI, NVIDIA. **Placeholder stubs that always report unavailable: Anthropic, Ollama.** Mock is allowed only outside production. | LLM layer | REPAIR (Ollama/Qwen, Anthropic) | Implement Ollama/Anthropic adapters when a runtime is reachable. Ollama is not reachable here. |
| Agent memory (key/value, user/agent/conversation/organisation scopes) | `models/agent.py:AgentMemory`, `/api/v1/memory` | Works. Lexical ranking. No embeddings. | Layer 4 (conversational memory) | KEEP | Keep as conversational/preference memory |
| Knowledge store (sources → versioned documents → chunks → per-run retrieved-context evidence) | `app/intelligence/`, `models/intelligence.py` | Workspace-scoped, provenance required, credentials rejected, freshness and expiry enforced. Retrieval persists `ai_retrieved_contexts`. **Used by the voice Brain path.** | Layer 4 (research/evidence memory) | KEEP / **EXTEND** | See B1 |
| **Knowledge ingestion** | `intelligence/ingestion.py` | `KnowledgeIngestionService` has **no caller**: no API, no worker, no job. In production nothing can enter the knowledge store, so Brain evidence retrieval always returns empty. | Layer 1 → Middle Layer 1 → Layer 4 | **INTEGRATE** | **B1 (highest-dependency blocker)** |
| Retrieval ranking | `intelligence/retrieval.py` | Term overlap only. No source reliability, no cross-reference weighting, no embeddings (no pgvector installed or used). | Layer 4 retrieval | EXTEND | Add reliability and corroboration weighting. pgvector is a later step. |
| Tools (internal catalogue: projects, tasks, CRM, analytics, weather, date, market price) | `app/tools/` | Permission-scoped and audited | Action layer | KEEP | none |
| Background jobs | `app/background/` | Scheduler, runner and dispatcher work. **`quant_research_summary` and `growth_content_review` return hard-coded mock results.** The planner routes QUANT intent to the mock job. The mock output does **not** reach the LLM prompt (only shaped evidence does), but it is recorded as a successful job. | Worker layer | REPAIR | Replace mock jobs with a real capability or remove them from routing |
| Integration connectors (Google Mail/Calendar, Slack, News, Search, …) | `integrations/connectors/catalog.py` | `DeterministicMockConnector`s. Real: Microsoft Graph (behind `MICROSOFT_INTEGRATION_ENABLED`). | Action layer | REPLACE (mocks) / KEEP (Microsoft) | Implement real connectors only when credentials and approvals exist |
| Voice gateway + experience events | `app/voice/`, `app/experience/` | Text-only boundary. Browser does STT/TTS. Durable sessions. Works end to end. | ARIMA OS interface → Brain | KEEP | none |
| Telegram transport | `app/telegram/` | Disabled by default. Verified identity mapping required. | Interface | KEEP | none |

### 3.3 Left Brain (financial/quant), FIC, risk, execution

| Component | Location | Current state / evidence | Class | Required action |
|---|---|---|---|---|
| Market data gateway (Twelve Data, Alpha Vantage), entitlement and licensing gates | `app/market/` | Fail-closed: availability endpoint is non-price, price/quote/candles routes are absent (404 over HTTP). **No live provider verified.** Credentials are absent and the host is blocked by network policy. | KEEP | Provider verification needs credentials, entitlement and network access |
| Instrument catalogue | `market/instruments.py` | 18 canonical instruments, closed set; ambiguous "oil" rejected | KEEP | none |
| QLab structural evidence (liquidity sweep / MSS / pullback) | `app/quant/` (570 LOC) | Strict contracts. `NEWS_BLOCKED` because no news provider exists. | KEEP | Needs the news source from B1 |
| Risk contract | `services/risk_contract.py` | Fail-closed. The prior zero-default finding is resolved. | KEEP | Needs authoritative daily-loss/exposure sources |
| QTrade execution | `services/trading_contracts.py` | `execution_enabled=True` **raises** in the constructor. Dry-run only. Every decision is audited. | KEEP | Needs a canonical execution-policy object (B2) |
| Ledger, deposits, trades, withdrawals, circuit breaker | `services/ledger.py`, `deposit_accounting.py`, `trade_accounting.py`, `routes/withdrawals.py` | Founder-operated manual accounting with provenance. Withdrawals are intake plus circuit breaker; no money moves. | KEEP | none |
| Backtest / Monte Carlo / walk-forward / stress | **absent here.** Present in Finance Engine v3 (`modules/monte_carlo_analytics.py`, `backtest_engine.py`, `walk_forward_analytics.py`) | Script-style, file-state, not tenant-aware | INTEGRATE | Port the pure computations behind tenant-aware contracts (B5) |
| Official macro/news sources | **absent here** (the audit's `NotConfiguredNewsProvider`). Present in v3 (`economic_calendar.py`, `official_news_cache.py`: BLS, Fed, BEA, Census, DOL, Conference Board) | Direct RSS fetches coupled to a Telegram bot | INTEGRATE | Feed through B1 ingestion as official-tier sources |
| FIC (intrinsic value, regimes, bubble, cross-asset) | **not found in any accessible repository.** Only `MarketRegime` enum and a 2-state regime heuristic in `quant/evidence.py`. | UNKNOWN / not built | Build after data ingestion exists |
| Right Brain (context, psychology, preferences) | **not present as a component.** User preferences can live in `AgentMemory(type=preference)`; nothing separates preference from financial fact. | not built | Add as a context evidence type that is never a financial input (B3 guard) |

### 3.4 Operations / founder / Jarvis / Laya

| Component | Location | State | Class | Required action |
|---|---|---|---|---|
| Founder Control Center | `services/founder_control.py`, `/api/v1/admin/founder/*` | System health (backend, DB, email, voice), data-feed provenance, voice diagnostics, workspace grants. Works over HTTP with TOTP. **Stale feed catalogue:** it says "No document storage" and "No portfolio data model", but both now exist. | EXTEND → Jarvis backend | Make it the Jarvis API: Brain status, sources, coverage, execution policy, Laya tasks |
| Laya (goal → task graph → agents → verification) | **not present.** Orchestration here is per-request. Background jobs are fixed schedules. The `tasks` module is a user to-do list, not a dependency graph. | not built | Build as a founder-only task graph with dependency enforcement (B4) |
| Jarvis UI | not in any accessible repo | UNKNOWN | — |

### 3.5 Surfaces outside this repo

| Surface | Evidence | Class |
|---|---|---|
| Website | `arima-early-access/index.html`: a single static page that posts to Google Apps Script, not connected to this backend. The cinematic website described in the prompt is not in any accessible repo. | UNKNOWN / EXTEND |
| ARIMA OS client app | Not accessible. The backend APIs exist: dashboard, portfolio, voice, documents, memory, notifications. | UNKNOWN |
| ARIMA World | Not accessible | UNKNOWN |
| PhoneCam | Not accessible | UNKNOWN |

## 4. Historical issues re-checked

| Historical issue | Current evidence |
|---|---|
| Stale cross-source worker state | No cross-source worker exists in any accessible repo. **Cannot verify.** |
| Authenticated retry/recovery | Refresh rotation and replay revocation verified over HTTP. The PostgreSQL retry helper exists (`services/postgres_retry.py`). |
| Missing database URL | Readiness returns 503 without a DB and 200 with one (verified). The migration chain is verified on PostgreSQL 16. |
| Docker/virtualization limits | Docker CLI is present but not used. Not needed: PostgreSQL ran natively. |
| Brain UI not the intended control UI | The UI is not accessible. The backend control surface is Founder Control. |
| World sparse urban fabric / performance / 12–20-user proof | **Not accessible — cannot verify.** |
| PhoneCam iPhone → Windows proof | **Not accessible — cannot verify.** Needs physical devices in any case. |
| Incomplete production verification | Production deployment URL/credentials are not available here. Production-like local verification is complete for the flows listed in §1. |

## 5. Execution posture (verified)

- `QTradeExecutionService(execution_enabled=True)` raises. There is no broker adapter. `DisabledQTradeExecution.submit_order` raises.
- No capital movement: withdrawals are intake and approval records behind a circuit breaker.
- Customer market prices are disabled (no price routes; availability is non-price).
- **Gap:** no single canonical object states `executionAuthority=NONE, liveExecution=false, autonomousExecution=false, paperExecution=true, externalExecution=DISCONNECTED`, and nothing tests it as an invariant. The posture is spread across constructors. This is B2.

## 6. Highest-dependency blockers (feed the execution graph)

1. **B1 — Layer 1 → Memory ingestion path missing.** Research, FIC, synthesis, source discovery and Jarvis source health all depend on validated sources entering the shared knowledge store. The store and retrieval exist; the entry point does not.
2. **B2 — Canonical execution policy.** Every financial path should assert one immutable policy, and Jarvis should display it.
3. **B3 — Right-brain guard.** Preferences and context must be typed so they can never become financial decision inputs.
4. **B4 — Laya task graph.** Needed for Jarvis → Laya → verified work with dependency enforcement.
5. **B5 — Quant simulation (Monte Carlo/stress).** Port the pure logic from Finance Engine v3.
6. **Infrastructure (outside code):** network policy blocks all external data hosts; there are no market or news credentials; Ollama is not reachable; World, PhoneCam, frontend and website repos are not accessible.
