# ARIMA Master Integration Plan v1.1 — Correction Memo

**Status:** ARCHITECTURAL ADDENDUM.
**Supersedes:** none. `ARIMA_MASTER_INTEGRATION_PLAN.md` v1.0 (sha256
`0ce13ff84cd0f2c81f4a945222b32fb96eb146cd2eb1a6f98abfb3d0a86cbe92`) remains
readable as historical record.
**Effective:** from this commit onward, until the authoritative 3-Sheet
specification is provided; the 3-Sheet, when received, supersedes both v1.0 and
this memo and requires a re-audit.
**Scope:** correct nine plan claims proven inaccurate by the Step 1 follow-up
audit (§1c/1d/1e). Do not rewrite v1.0; preserve it verbatim.

## Rule of authority

1. **3-Sheet (when provided)** — product source of truth.
2. **Repository evidence** — implementation reality. Where the plan contradicts
   verified repository architecture, correct the plan; do not corrupt the
   architecture.
3. **Roadmap V2** — temporary execution reference for phase intent + Laya
   content templates, per the earlier authority change.
4. **Master Integration Plan v1.0** — temporary phase/step order.
5. **This memo (v1.1)** — corrections applied over v1.0.

Never implement an inaccurate requirement merely because it appears in the
older plan. Never overwrite the existing architecture to satisfy a stale
claim.

## Corrections

### C1. Plan v1.0 §1.1 residence API assumption

- **v1.0 stated:** Executive OS must expose
  `GET /api/v1/brain/world/residences`,
  `GET /api/v1/brain/world/residences/{villa_id}`,
  and `POST /api/v1/brain/world/recommend`.
- **Repository reality:** the 190 residences are not a dataset; they are
  deterministic client-side geometry produced by
  `aryan-portfolio-local/lib/world-model.ts::createResidenceManifest()` and
  covered by `tests/world-city-architecture.test.ts` (`expect(buildings).
  toHaveLength(190)`). Per-user villa content is owned by the dedicated
  `world-service` (SQLite-backed), exposed as
  `worldApi('villas/VILLA-####')` through the tenant/user-scoped world
  gateway. Node Brain's contract
  (`ARCHITECTURE_SERVICE_BOUNDARIES.md`,
  `BRAIN_INTERNAL_API_CONTRACT.md`,
  `AGENT_SYSTEM.md`, `FINANCIAL_INTELLIGENCE_CORE.md`) does not include
  world/villa/residence.
- **Correction:** Do NOT add `/api/v1/brain/world/*` or `/brain/v1/world/*`
  residence endpoints. Residence presentation is client code; per-user villa
  content already has an API through world-service.

### C2. Plan v1.0 §1.2 duplicate `lib/arima-api.ts` assumption

- **v1.0 stated:** create `apps/world/lib/arima-api.ts` (a new `ArimaAPI`
  class with `login`, `askBrain`, `getResidences`, ...).
- **Repository reality:** `aryan-portfolio-local` already has a mature
  authenticated client stack —
  `lib/api-client.ts` (bearer + CSRF + 401 refresh + correlation-id),
  `lib/auth-api.ts` (`getAccessToken`, `getCsrfToken`,
  `refreshCsrfToken`, refresh via `navigator.locks`),
  `lib/world-api.ts` (world-service),
  plus 12 domain-specific `*-api.ts` wrappers (dashboard, portfolio,
  projects, tasks, activity, notifications, intelligence,
  microsoft-integration, founder, tasks, withdrawal-intake, world).
- **Correction:** Do NOT create `lib/arima-api.ts`. Extend the existing
  clients when a genuine new endpoint appears.

### C3. Plan v1.0 §1.3 "residences load from API instead of local JSON" assumption

- **v1.0 stated:** replace hardcoded data with API calls; residences load from
  API not local JSON.
- **Repository reality:** the JSON at
  `aryan-portfolio-local/docs/data/arima-world-residences.json` is an
  engineering spec (`schema: arima-world-residence-manifest/v1`). `grep -r
  arima-world-residences` returns zero runtime references. Residences at
  runtime come from `createResidenceManifest()` code, which the app already
  imports and uses.
- **Correction:** No change required in `DistrictCity.tsx` or
  `PremiumResidenceField.tsx` to satisfy this criterion. Mark v1.0 §1.3 as
  factually not applicable and move on.

### C4. Stale Executive-OS description (Flask, 97 commits)

- **v1.0 stated (mirroring V2):** "Flask backend, 97 commits."
- **Repository reality:** FastAPI backend on `main` @ `79a21bd`, 67 commits.
  `app/main.py` imports `from fastapi import FastAPI` and defines lifespan
  + CORS + trusted-host + correlation-id middleware. 26 alembic migrations,
  563 tests in the collected inventory as of 2026-09-17.
- **Correction:** In all subsequent plan artefacts, describe Executive-OS as
  FastAPI (Python 3.12+, SQLAlchemy 2 async, asyncpg, Alembic), 67 commits at
  the time of this memo, deployed via `railway.toml`. Do not modify
  Executive-OS code to satisfy V2/v1.0's Flask assumption.

### C5. "Node Brain is merely an unbuilt directory"

- **v1.0 stated (§L34-40):** "Brain: directory structure created, not built.
  Has brain/ folder in Executive-OS."
- **Repository reality:** `Arima-Brain-AUTHORITATIVE` is an actively developed
  Node.js monorepo — `brain-v0.3`/`v0.5`/`v0.8`, 545 files, 103 docs, 46 SQL
  migrations with pgvector, a formal `brain.internal.v1` contract, a live
  local runtime tied to Ollama `qwen2.5:1.5b-instruct`, and a stable API at
  `/brain/v1/{capabilities, context}` plus `/control-plane/*`,
  `/sources/*`, `/identity`, `/auth/*`. The Executive-OS `app/brain/` folder
  from the Windows Codex sandbox is an uncommitted Laya HTTP client, not the
  Brain.
- **Correction:** The **Node Brain is the Brain**. All Brain-flavoured
  requirements from v1.0 that assumed a new Python Brain must be re-routed to
  the Node Brain via the Executive-OS bridge already committed on
  `feature/brain-integration` (`9cb02b8`). Any perceived "missing" Brain
  capability must be checked against `Arima-Brain-AUTHORITATIVE` before
  building anything.

### C6. Three-service World architecture (correct topology)

Correct, evidence-backed topology:

```
┌──────────────────────────────────────────────────────────────────────┐
│ ARIMA World client (aryan-portfolio-local, Next.js/React)             │
│  • lib/world-model.ts createResidenceManifest() — 190 slots (code)    │
│  • public/assets/environment/architecture/district01/*.glb — geometry │
│  • components/world/* — 3D scene                                       │
└──────────────┬──────────────────────────────┬────────────────────────┘
               │                              │
   ┌───────────▼───────────┐      ┌───────────▼──────────────────────┐
   │ world-service         │      │ Executive OS (FastAPI)            │
   │  Node.js in-repo      │      │  /api/v1/*                        │
   │  SQLite + .world-data │      │  (auth, dashboard, portfolio,     │
   │  Whitelisted routes:  │      │   projects, tasks, activity,      │
   │   me, logout,         │      │   notifications, intelligence,    │
   │   presence,           │      │   admin/founder, market,          │
   │   preferences,        │      │   research, voice, withdrawals)   │
   │   operations,         │      └───────┬──────────────────────────┘
   │   villas/VILLA-####,  │              │
   │   ai/{quota,start,    │              │  new /api/v1/brain/*
   │   stop,message},      │              │  (fail-closed bridge —
   │   events/*,           │              │   already committed)
   │   invitations/redeem  │              │
   │  Auth: 43-char        │              ▼
   │   base64url cookie    │      ┌───────────────────────────────────┐
   │  Reached via          │      │ Node Brain                        │
   │   /api/world/*        │      │  Arima-Brain-AUTHORITATIVE        │
   │   → lib/world-gateway │      │  Financial intelligence only:     │
   │   → ARIMA_WORLD_      │      │   sources, evidence, knowledge,   │
   │   ACCESS_ORIGIN       │      │   research, memory, quant,        │
   │  LLM: OpenAI          │      │   backtests, portfolio/risk,      │
   │   Responses API +     │      │   decision artifacts, paper       │
   │   Whisper             │      │   execution, alerts               │
   └───────────────────────┘      │  LLM: Ollama qwen2.5:1.5b-instruct│
                                  │  Contract: brain.internal.v1      │
                                  │  Endpoints:                       │
                                  │   /brain/v1/capabilities          │
                                  │   /brain/v1/context (GET, POST)   │
                                  │   /auth/*, /identity,             │
                                  │   /control-plane/*, /sources/*    │
                                  └───────────────────────────────────┘
```

This memo names four services, not two. Node Brain is scope-restricted to
**financial intelligence** only.

### C7. Correct API boundaries between the four services

| Traffic | Path | Auth | Scope |
|---|---|---|---|
| Client → Executive OS (customer product) | `/api/v1/*` | JWT bearer + CSRF double-submit + refresh cookie | Account, workspace, dashboard, portfolio, tasks, projects, activity, notifications, intelligence, market, voice, withdrawals, admin/founder |
| Client → world-service (World runtime) | `/api/world/*` (whitelist regex) → `world-gateway` → `${ARIMA_WORLD_ACCESS_ORIGIN}/api/v1/world/*` | 43-char base64url `arima_world_session` cookie (HttpOnly, SameSite=Strict, 8h) + `X-ARIMA-World: 1` + origin check | Presence, per-user villa content, ai/*, events/*, preferences, operations |
| Executive OS → Node Brain (private) | `/internal/v1/brain/*` on Node Brain (suggested) — reached via bridge from `/api/v1/brain/*` on Executive OS | Service credential (Bearer) + `X-Contract-Version: brain.internal.v1` + envelope `serviceIdentity`, `tenantContext`, `userContext`, `correlationId`, `idempotencyKey` | Brain capabilities, context, future decision/research/evidence endpoints |
| world-service → Node Brain (future, IF ever needed) | server-to-server, envelope-signed | Same as Executive OS → Brain, distinct `serviceIdentity` | Only if a legitimate financial Brain capability is required from World (currently none) |

Public Website (`aryan-portfolio`) and Customer App (`aryan-portfolio-local`)
never call Node Brain directly; the Executive OS is the customer policy
boundary.

### C8. 190-residence presentation geometry is code; per-user villa content is data

- **Presentation geometry** for VILLA-0001..VILLA-0190: deterministic code in
  `lib/world-model.ts`, tests in `tests/world-city-architecture.test.ts`,
  static GLBs in `public/assets/environment/architecture/district01/`.
  Deployment ships this as-is; no backend fetch.
- **Per-user villa content** (assignment, archetype, floors, preferences):
  world-service SQLite, keyed by `(tenant, villa_id, user)`, retrieved via
  `worldApi('villas/VILLA-####')`. Tenant-scoped and user-scoped.
- **Manifest JSON** (`docs/data/arima-world-residences.json`): engineering
  reference only; not read at runtime; keep it under `docs/data/` as
  documentation.

These three facets have different owners and must not be merged.

### C9. Future Brain capabilities must stay within financial-intelligence scope

Any new Brain capability must be justified against the Brain's declared scope
in `docs/BRAIN_INTERNAL_API_CONTRACT.md` and
`docs/ARCHITECTURE_SERVICE_BOUNDARIES.md`. Presentation, per-user allocation,
UI state, invitations, event scheduling, and educational content stay out of
the Brain. Cross-cutting concerns (evidence, research, quant, risk, decision
artefacts, memory, advisory) may enter the Brain only as new
`/brain/v1/{capability}` endpoints with envelope-signed service calls.

## What v1.0 remains correct on

- Step 1's overall goal (connect a first frontend to a Brain API surface via
  a fail-closed bridge). **Executed at commit `9cb02b8`.**
- ONE Brain principle: no product builds its own intelligence.
- Laya-first classification, graceful fallback, permission control, context
  matters, preference ≠ financial fact — all preserved.
- Safety baseline: `executionAuthority=NONE`, `liveExecution=false`,
  `autonomousExecution=false`, `paperExecution=true`,
  `externalExecution=DISCONNECTED`.

## Version pin

Effective architecture snapshot at time of writing:

- `Arima-Executive-OS` @ `feature/brain-integration` `9cb02b8`
  (branched from `main` @ `79a21bd`), 8 files added, 754 lines,
  9/9 bridge tests green, `execution_authority=NONE`.
- `Arima-Brain-AUTHORITATIVE` @ `arima-brain-local` `5f8c3de`
  (read-only in this session).
- `aryan-portfolio` @ `main` `c53c650` — read-only in this session.
- `aryan-portfolio-local` @ `main` `4c92afc` (working copy at
  `/mnt/user-data/working/arima-world-190-villas/`) — read-only in this
  session.
- Laya standalone @ its own repo — read-only, **FROZEN**.
- Arima-auto @ its own tree — read-only.

When the authoritative 3-Sheet arrives, re-audit every row above and update.
