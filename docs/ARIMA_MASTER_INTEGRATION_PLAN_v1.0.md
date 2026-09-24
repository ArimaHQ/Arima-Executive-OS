# ARIMA — MASTER INTEGRATION PLAN
## One Brain. One Ecosystem. Everything Connected.

> **Give this to Claude Code.**
> This document tells Claude Code how to connect Executive-OS, ARIMA World, Brain, and all interfaces into a single working ecosystem.

---

# WHAT WE HAVE RIGHT NOW

```
┌─────────────────────────────────────────────────────────┐
│                    WHAT EXISTS                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. EXECUTIVE-OS (Backend)                              │
│     Repo: ArimaHQ/Arima-Executive-OS                    │
│     Tech: FastAPI + SQLAlchemy + Alembic                 │
│     Branch: feature/laya-intent-engine                   │
│     Status: Phase 0 done — Laya IntentEngine wired      │
│     Deploy: Railway                                      │
│     Has: Auth, routes, services, models, orchestration   │
│                                                         │
│  2. ARIMA WORLD (Frontend/3D)                           │
│     Location: local working copy                         │
│     Tech: Next.js + TypeScript + React                   │
│     Has: 190 villas, 3D assets (GLB/Blender),            │
│          PremiumResidenceField, DistrictCity,             │
│          amphitheatre, district01 architecture            │
│     Domain: arimafinance.xyz                             │
│     Status: reconstructed, not deployed                  │
│                                                         │
│  3. LAYA (Local AI)                                     │
│     Status: integrated as IntentEngine                   │
│     Role: System 1 fast decisions (33ms)                 │
│                                                         │
│  4. BRAIN                                               │
│     Status: directory structure created, not built       │
│     Has: brain/ folder in Executive-OS                   │
│                                                         │
│  5. ARIMA OS (Client App Frontend)                      │
│     Status: does not exist yet                           │
│                                                         │
│  6. WEBSITE                                             │
│     Status: arima-early-access (basic HTML)              │
│                                                         │
│  7. JARVIS                                              │
│     Status: does not exist yet                           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

# THE TARGET: ONE ECOSYSTEM

```
                        ┌──────────────┐
                        │  ARIMA BRAIN │
                        │  (ONE BRAIN) │
                        └──────┬───────┘
                               │
                    ┌──────────┼──────────┐
                    │          │          │
              ┌─────┴─────┐   │   ┌──────┴──────┐
              │ LEFT BRAIN│   │   │ RIGHT BRAIN │
              │ Quant/Fin │   │   │ Human/Ctx   │
              └─────┬─────┘   │   └──────┬──────┘
                    │    ┌────┴────┐     │
                    └────┤ MIDDLE  ├─────┘
                         │ BRAIN   │
                         └────┬────┘
                              │
                     ┌────────┴────────┐
                     │   API LAYER     │
                     │ /api/v1/brain/* │
                     └────────┬────────┘
                              │
          ┌───────────┬───────┼───────┬────────────┐
          │           │       │       │            │
     ┌────┴───┐ ┌────┴──┐ ┌──┴───┐ ┌─┴──────┐ ┌──┴──────┐
     │ARIMA OS│ │WEBSITE│ │WORLD │ │JARVIS  │ │SERVICES │
     │Client  │ │Public │ │Immrv │ │Founder │ │Finance  │
     │App     │ │       │ │      │ │        │ │         │
     └────────┘ └───────┘ └──────┘ └────────┘ └─────────┘
```

**Rule: Every interface talks to the SAME Brain through the SAME API. No separate brains.**

---

# INTEGRATION ARCHITECTURE

## Monorepo Structure (Target)

```
ARIMA/
├── apps/
│   ├── api/                          # Executive-OS (FastAPI) — EXISTS
│   │   ├── app/
│   │   │   ├── brain/                # ARIMA Brain — BUILDING
│   │   │   │   ├── left/
│   │   │   │   ├── right/
│   │   │   │   ├── middle/
│   │   │   │   ├── layers/
│   │   │   │   ├── laya_client.py    # EXISTS (Phase 0)
│   │   │   │   └── pipeline.py
│   │   │   ├── models/               # EXISTS
│   │   │   ├── routes/               # EXISTS
│   │   │   │   ├── auth.py           # EXISTS
│   │   │   │   ├── brain.py          # NEW — Brain API endpoints
│   │   │   │   ├── world.py          # NEW — World API endpoints
│   │   │   │   └── jarvis.py         # NEW — Founder endpoints
│   │   │   ├── services/             # EXISTS
│   │   │   └── orchestration/        # EXISTS (IntentEngine here)
│   │   ├── tests/                    # EXISTS
│   │   └── requirements.txt          # EXISTS
│   │
│   ├── world/                        # ARIMA World — EXISTS (Next.js)
│   │   ├── components/
│   │   │   └── world/
│   │   │       ├── city/
│   │   │       │   ├── PremiumResidenceField.tsx
│   │   │       │   └── DistrictCity.tsx
│   │   │       └── shared/
│   │   ├── docs/data/
│   │   │   └── arima-world-residences.json
│   │   ├── public/assets/            # 3D models, textures
│   │   ├── lib/
│   │   │   └── api.ts                # NEW — connects to Brain API
│   │   └── package.json
│   │
│   ├── os/                           # ARIMA OS Client — TO BUILD
│   │   └── (Next.js app)
│   │
│   ├── website/                      # Public Website — TO BUILD
│   │   └── (Next.js app)
│   │
│   └── jarvis/                       # Founder Dashboard — TO BUILD
│       └── (Next.js app)
│
└── packages/
    ├── shared-types/                 # TypeScript types
    └── arima-api-client/             # Shared API client for all frontends
```

---

# EXECUTION PLAN — STEP BY STEP

## STEP 1: CONNECT ARIMA WORLD TO EXECUTIVE-OS API

**Priority: HIGH — this connects the first frontend to the backend.**

### 1.1 — Create Brain API Endpoints in Executive-OS

```python
# app/routes/brain.py — NEW FILE

from fastapi import APIRouter, Depends
from app.brain.pipeline import BrainPipeline
from app.auth import get_current_user

router = APIRouter(prefix="/api/v1/brain", tags=["brain"])

@router.post("/ask")
async def ask_brain(query: BrainQuery, user=Depends(get_current_user)):
    """Natural language query to the Brain."""
    # 1. Laya classifies intent (33ms)
    # 2. Routes to appropriate brain component
    # 3. Returns structured + natural language answer
    pass

@router.get("/market/{asset}")
async def market_intelligence(asset: str, user=Depends(get_current_user)):
    """Market analysis for an asset (gold, BTC, etc.)."""
    pass

@router.get("/world/residences")
async def get_residences(user=Depends(get_current_user)):
    """List ARIMA World residences with Brain-powered recommendations."""
    pass

@router.get("/world/residences/{villa_id}")
async def get_residence(villa_id: str, user=Depends(get_current_user)):
    """Single residence details + Brain context."""
    pass

@router.post("/world/recommend")
async def recommend_residence(preferences: dict, user=Depends(get_current_user)):
    """Brain recommends residences based on user context."""
    # Right Brain: user preferences
    # Left Brain: financial analysis (can they afford it?)
    # Middle Brain: synthesize recommendation
    pass
```

### 1.2 — Create API Client in ARIMA World

```typescript
// apps/world/lib/arima-api.ts — NEW FILE

const API_BASE = process.env.NEXT_PUBLIC_ARIMA_API_URL || 'http://localhost:8000';

export class ArimaAPI {
  private token: string | null = null;

  async login(email: string, password: string) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    this.token = data.access_token;
    return data;
  }

  async askBrain(query: string) {
    return this.authedFetch('/api/v1/brain/ask', {
      method: 'POST',
      body: JSON.stringify({ query })
    });
  }

  async getResidences(filters?: Record<string, any>) {
    const params = new URLSearchParams(filters);
    return this.authedFetch(`/api/v1/brain/world/residences?${params}`);
  }

  async getResidence(villaId: string) {
    return this.authedFetch(`/api/v1/brain/world/residences/${villaId}`);
  }

  async getRecommendations(preferences: Record<string, any>) {
    return this.authedFetch('/api/v1/brain/world/recommend', {
      method: 'POST',
      body: JSON.stringify(preferences)
    });
  }

  private async authedFetch(path: string, options: RequestInit = {}) {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
        ...options.headers,
      }
    });
    return res.json();
  }
}

export const arimaApi = new ArimaAPI();
```

### 1.3 — Wire World Components to API

In `PremiumResidenceField.tsx` and `DistrictCity.tsx`:
- Replace any hardcoded data with API calls
- Add Brain-powered search/filter
- Add recommendation section

### 1.4 — CORS Configuration

In Executive-OS `app/config.py`:
```python
CORS_ORIGINS = [
    "http://localhost:3000",        # World dev
    "http://localhost:3001",        # OS dev
    "http://localhost:3002",        # Jarvis dev
    "https://arimafinance.xyz",    # World production
]
```

### Exit Criteria — Step 1
- [ ] World app can authenticate against Executive-OS API
- [ ] Residences load from API (not just local JSON)
- [ ] Brain endpoint responds to natural language queries
- [ ] CORS works between World (Next.js) and API (FastAPI)

---

## STEP 2: BUILD THE BRAIN PIPELINE

**Priority: HIGH — this is the core intelligence.**

### 2.1 — Brain Pipeline Manager

```python
# app/brain/pipeline.py

class BrainPipeline:
    """
    Central Brain orchestrator.
    All interfaces connect through this — no separate brains.
    """
    def __init__(self, laya_engine, claude_client, memory):
        self.laya = laya_engine          # System 1 (fast, local)
        self.claude = claude_client       # System 2 (deep, API)
        self.memory = memory             # Layer 4
        self.left_brain = LeftBrain()
        self.right_brain = RightBrain()
        self.middle_brain = MiddleBrain()

    async def process(self, query: str, user_context: dict) -> BrainResponse:
        """
        Main entry point. Every query goes through this.
        """
        # 1. Laya classifies intent (33ms)
        intent = await self.laya.classify_intent(query)

        # 2. Laya routes to brain component
        routing = await self.laya.route_to_brain(query)

        # 3. Based on routing:
        if routing == "direct":
            return await self.memory.quick_answer(query)

        if routing == "left_brain":
            analysis = await self.left_brain.analyze(query, user_context)
        elif routing == "right_brain":
            context = await self.right_brain.contextualize(query, user_context)
            analysis = context
        else:  # "both"
            left = await self.left_brain.analyze(query, user_context)
            right = await self.right_brain.contextualize(query, user_context)
            analysis = {"left": left, "right": right}

        # 4. Middle Brain synthesizes
        decision = await self.middle_brain.synthesize(
            query=query,
            analysis=analysis,
            user_context=user_context,
            intent=intent
        )

        # 5. Store in memory
        await self.memory.store(query, decision)

        return decision
```

### 2.2 — Left Brain (Starter)

```python
# app/brain/left/engine.py

class LeftBrain:
    """Financial / Quantitative Intelligence"""

    async def analyze(self, query: str, context: dict):
        # Phase 1: Basic market analysis using Claude API
        # Phase 2+: Add quant models, backtesting, etc.
        pass

    async def market_analysis(self, asset: str):
        """Current market analysis for an asset."""
        pass

    async def financial_model(self, user_data: dict):
        """Cash flow, budget, portfolio analysis."""
        pass
```

### 2.3 — Right Brain (Starter)

```python
# app/brain/right/engine.py

class RightBrain:
    """Human / Contextual Intelligence"""

    async def contextualize(self, query: str, user_context: dict):
        # Understand what this query means for THIS user
        # Check upcoming obligations, preferences, risk tolerance
        pass

    async def get_user_context(self, user_id: str):
        """Gather all context about this user."""
        pass
```

### 2.4 — Middle Brain (Starter)

```python
# app/brain/middle/engine.py

class MiddleBrain:
    """Decision / Neural Core — combines Left + Right"""

    async def synthesize(self, query, analysis, user_context, intent):
        # Combine financial analysis with human context
        # Use Claude API for complex synthesis
        # Use Laya for confidence gating
        pass
```

### Exit Criteria — Step 2
- [ ] BrainPipeline.process() handles a query end-to-end
- [ ] Laya routes queries correctly (left/right/both/direct)
- [ ] Claude API integration works for synthesis
- [ ] Basic Left Brain returns market analysis
- [ ] Basic Right Brain returns user context
- [ ] Middle Brain combines both into a decision
- [ ] 15+ tests pass

---

## STEP 3: ARIMA OS — CLIENT APP

**Priority: MEDIUM — the main client interface.**

### 3.1 — Create Next.js App

```bash
cd apps/
npx create-next-app@latest os --typescript --tailwind --app
```

### 3.2 — Core Pages
- `/` — Dashboard (net worth, cash flow, budget)
- `/transactions` — Transaction management
- `/budget` — Budget tracking
- `/portfolio` — Investment portfolio
- `/chat` — AI chat with Brain
- `/settings` — User settings

### 3.3 — AI Chat Component
The chat connects to `/api/v1/brain/ask`:
- User types question
- Laya classifies intent (shown as "thinking...")
- Brain processes
- Response shown as text + cards + charts

### 3.4 — Connect to Same API as World
Use the same `arima-api-client` package.

### Exit Criteria — Step 3
- [ ] OS app runs on localhost:3001
- [ ] Dashboard shows financial data from API
- [ ] AI chat works with Brain
- [ ] Authentication works
- [ ] Basic responsive design

---

## STEP 4: JARVIS — FOUNDER DASHBOARD

**Priority: MEDIUM-LOW — important but after OS.**

### 4.1 — Create Next.js App

```bash
cd apps/
npx create-next-app@latest jarvis --typescript --tailwind --app
```

### 4.2 — Core Pages
- `/` — System health dashboard
- `/brain` — Brain monitoring (recent decisions, confidence scores)
- `/sources` — Source management (Layer 1)
- `/users` — User analytics
- `/gaps` — Knowledge gap detection
- `/world` — World analytics (villa views, interest, etc.)

### 4.3 — Founder-Only Auth
Jarvis login checks `role === "founder"`. All others rejected.

### Exit Criteria — Step 4
- [ ] Jarvis runs on localhost:3002
- [ ] Only founder can access
- [ ] System health shows real data
- [ ] Brain monitoring shows recent queries and decisions

---

## STEP 5: WEBSITE — PUBLIC LAYER

**Priority: LOW for now — arimafinance.xyz basic is enough.**

### 5.1 — Upgrade arima-early-access
- Landing page with ARIMA description
- Public research/publications (from Brain, curated)
- Sign up → redirects to ARIMA OS
- Login → redirects to ARIMA OS

---

## STEP 6: FULL INTEGRATION TEST

### 6.1 — End-to-End Flow Test
```
User visits arimafinance.xyz (Website)
  → Signs up
  → Redirected to ARIMA OS
  → Adds financial data (income, expenses, goals)
  → Brain analyzes their situation
  → Asks: "Should I invest in gold?"
    → Laya: intent=analysis, route=both (33ms)
    → Left Brain: gold market analysis
    → Right Brain: user has rent due in 3 days, low liquidity
    → Middle Brain: "Gold looks interesting but your rent is due Friday.
       Consider waiting until after your obligations are met."
  → Visits ARIMA World
    → Browses villas
    → Brain recommends villas based on preferences + budget
  → Founder checks Jarvis
    → Sees all queries, brain health, knowledge gaps
```

### 6.2 — API Integration Test
Every frontend calls the same `/api/v1/brain/*` endpoints.
No frontend has its own intelligence.

### Exit Criteria — Step 6
- [ ] Full user journey works (Website → OS → World → Brain)
- [ ] Founder journey works (Jarvis → Brain monitoring)
- [ ] ONE Brain serves all interfaces
- [ ] Laya + Claude API work together (System 1 + System 2)

---

# EXECUTION ORDER FOR CLAUDE CODE

```
STEP 1: Connect World ↔ API          ← START HERE
  ├── Brain API endpoints
  ├── API client in World
  ├── CORS setup
  └── Test: World loads data from API

STEP 2: Build Brain Pipeline          ← CORE
  ├── Pipeline manager
  ├── Left Brain (starter)
  ├── Right Brain (starter)
  ├── Middle Brain (starter)
  └── Test: Brain answers queries

STEP 3: ARIMA OS (Client App)         ← MAIN INTERFACE
  ├── Next.js app
  ├── Dashboard + Transactions + Budget
  ├── AI Chat with Brain
  └── Test: OS works with Brain

STEP 4: Jarvis (Founder)              ← MONITORING
  ├── Next.js app
  ├── System health + Brain monitoring
  └── Test: Founder can see everything

STEP 5: Website                       ← PUBLIC
  ├── Upgrade landing page
  └── Test: Sign up → OS redirect

STEP 6: Integration Test              ← VERIFY ALL
  └── Full ecosystem test
```

---

# CLAUDE CODE PROMPT

Give Claude Code this instruction:

```
Read the ARIMA Master Integration Plan.
The goal: ONE Brain, ONE Ecosystem. Every interface (OS, World, Website, Jarvis)
connects to the same Brain through the same API.

Current state:
- Executive-OS: FastAPI backend at ArimaHQ/Arima-Executive-OS,
  branch feature/laya-intent-engine (Laya IntentEngine done)
- ARIMA World: Next.js app at /path/to/arima-world-190-villas/
  (190 villas, 3D assets, not connected to API)
- Laya: integrated as IntentEngine, default off
- Brain: directory structure exists, pipeline not built

Start with Step 1: Connect ARIMA World to Executive-OS API.
Create Brain API endpoints. Create API client in World.
Set up CORS. Test the connection.

Then move to Step 2: Build the Brain Pipeline.
Then Step 3, 4, 5, 6 in order.

Test everything at each step.
Do not build separate brains for any product.
ONE BRAIN through ONE API.
```

---

# KEY PRINCIPLES (NEVER BREAK THESE)

1. **ONE BRAIN** — No product builds its own intelligence
2. **API LAYER** — Every frontend talks to `/api/v1/brain/*`
3. **LAYA FIRST** — Every query hits Laya (33ms) before Claude API
4. **PERMISSION CONTROL** — Client sees their data, Founder sees everything
5. **GRACEFUL FALLBACK** — If Laya is down → keywords. If Claude API is down → cached answers.
6. **CONTEXT MATTERS** — Right Brain context always consulted before financial decisions
7. **Preference ≠ Financial Fact** — Never treat inferred preferences as confirmed data

---

*Document version: 1.0*
*This connects: Executive-OS + ARIMA World + Brain + OS + Jarvis + Website*
*Into: ONE ARIMA ECOSYSTEM*
