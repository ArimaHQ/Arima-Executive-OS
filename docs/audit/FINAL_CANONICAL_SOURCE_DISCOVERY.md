# Final Canonical Source Discovery & Reconciliation Report

**Date:** 2026-09-24
**Scope:** Filesystem/workspace discovery for ARIMA Brain, ARIMA World, Website, ARIMA OS, and PhoneCam, previously reported by an earlier audit as "inaccessible." Discovery-only — no application code was modified, moved, renamed, or deleted. This report is the only artifact created by this pass.
**Environment:** Windows 10 Home x64 (build 19045), user home `C:\Users\Arima Finance`, single mounted drive `C:` (no other drives/mounts present).
**Method note:** Most findings were verified directly via `git`/filesystem/`sha256sum` commands run in this pass. The ARIMA OS section (§4) was first produced by a delegated sub-agent, then spot-checked directly (branch, last-commit hash, and file layout independently re-confirmed) before inclusion here. Mid-discovery, several delegated sub-agents entered a self-referential identity-confusion loop (forked agents that inherited full parent context each began asserting they were the coordinating session). That loop was abandoned in favor of direct verification; it produced no findings and is noted here only for traceability, not as evidence.

---

## 0. Sought reference documents — NOT FOUND locally

An exhaustive recursive search of the entire user home directory (`C:\Users\Arima Finance`, all subfolders, all drives available) was run for the following. None were found anywhere on this machine:

- `ARIMA_SYSTEM_AUDIT.md` — not found.
- `ARIMA_EXECUTION_GRAPH.md` — not found.
- "The 3 authoritative ARIMA sheets" — no locally-stored artifact matches this name. The closest analog found is the canonical-ownership forensic series inside `ARIMA-FINANCE-CONTROL-CENTER` (see §5), dated 2026-09-16/17, which performs a similar canonicality exercise but is not labeled as "3 sheets" and does not resolve to 3 documents.

**Action needed from the user:** confirm where these three artifacts live (a different repo, a cloud doc store, or a different machine), or confirm this report should serve as their replacement/update.

---

## 1. ARIMA Brain

### 1a. Arima-Brain-AUTHORITATIVE (primary candidate)
- **PATH:** `C:\Users\Arima Finance\Documents\Codex\ARIMA-PC-MIGRATION-WORK\ARIMA\Arima-Brain-AUTHORITATIVE`
- **REPOSITORY:** git repo, local only in this pass (no remote checked — see blockers); package name `arima-finance` ("ARIMA Finance — Data Fabric v0.3")
- **BRANCH:** `arima-brain-local`
- **LAST COMMIT:** `5f8c3de41c2098a8ab3ff9abb85a9f60159fb0ac` — 2026-09-06 16:16:00 +0100 — "Plan ARIMA Dedicated Brain PostgreSQL Provisioning"
- **WORKING TREE:** dirty — modified: `apps/web/app.js`, `apps/web/styles.css`, `brain/api/server.js`, `brain/config.js`, `brain/database.js` (uncommitted)
- **BUILD/RUNTIME STATUS:** Confirmed by direct file read, exact matches to every search term in the discovery brief:
  - `docs/LOCAL_RUNTIME.md` present (sha256 `6717058e...90f4ac`) — documents `scripts/start-brain-local.ps1` (present on disk) as the launcher; starts ordered migrations, the Brain API, and Ollama `qwen2.5:1.5b-instruct` over loopback; execution authority forced `NONE`.
  - `docs/agent-mapping-175-20260918.json` (sha256 `b81e68aa...6f59a3a`) — `"totalDefinitions": 175` (the "175 declarative agents"). `activeWorkers`: `ecb-macro-agent`, `bbc-news-agent`, `cross-source-analysis-agent`, `data-quality-agent`, `macro-analysis-agent`, `news-analysis-agent` — exact match to ECB/BBC/cross-source/data-quality worker search terms.
  - `docs/SOURCES.md` confirms `ecb-exchange-rates` (ECB Data Portal SDMX) and `bbc-news-rss` (BBC News RSS) as live source definitions.
  - `docs/final-implementation-gate-2026-09-21.json` (latest status doc): brain API healthy (`/health`, `/health/dependencies`, `/ready` all 200), 48/48 schema migrations applied, worker runtime alive with all 6 registered workers `HEALTHY` after a genuine restart cycle. Overall self-classification: **PARTIAL** (six capability families remain gated on source-approval/authenticated-scope boundaries; all financial execution controls disabled by design).
  - `.ollama\models\manifests\registry.ollama.ai\library\qwen2.5\1.5b-instruct` confirmed present on this machine — Ollama + the exact model this Brain expects is installed.
- **TEST STATUS:** Not re-run in this pass. Latest status doc claims a verified post-restart health cycle for all 6 workers; no independent test-suite run performed here.
- **RELATION TO AUTHORITATIVE SHEETS:** Prior forensic doc `ARIMA-FINANCE-CONTROL-CENTER\ARIMA_CANONICAL_OWNERSHIP_REPORT.md` (sha256 `994c48f4...6ede3c`) tags this exact path `Canonical: NON_CANONICAL_COPY / HIGH` confidence — despite the directory name containing "AUTHORITATIVE." Naming does not equal canonical status per that prior audit.
- **KEEP/INTEGRATE/EXTEND/REPAIR/REPLACE:** **KEEP** — functioning, well-documented, matches every discovery search term exactly.
- **BLOCKERS:** Canonical-ownership status is explicitly disputed by prior forensic audit despite the folder name; uncommitted working tree; no remote-tracking status verified in this pass.

### 1b. Arima-Brain (secondary/parallel copy, different stack)
- **PATH:** `C:\Users\Arima Finance\Documents\Codex\ARIMA-PC-MIGRATION-WORK\ARIMA\Arima-Brain`
- **REPOSITORY:** git repo, Python/FastAPI stack (pyproject.toml, requirements.txt, alembic.ini) — architecturally different from 1a (Node.js)
- **BRANCH:** `validation/temp-exact-candidate-actions-20260826`
- **LAST COMMIT:** `ec33d75b7737dab7f273be58dbc4ffbbaa2ceae2` — 2026-08-24 13:34:48 +0100 — "feat: add founder read-only trade provenance"
- **WORKING TREE:** dirty — modified: `app/api/v1/router.py`, `app/core/config.py`, `app/email/factory.py`, `app/email/providers/__init__.py`, `tests/test_email_configuration.py`
- **BUILD/RUNTIME STATUS:** Has `.venv` populated, `.pytest_cache` present, local sqlite auth db and uvicorn log present (`local-uvicorn.log`, last written 2026-09-19) — was run locally at some point.
- **TEST STATUS:** `.pytest_cache` present; not re-run in this pass.
- **RELATION TO AUTHORITATIVE SHEETS:** Not the same codebase as 1a; role vs. 1a is unresolved (parallel migration attempt vs. superseded prototype — not determined in this pass).
- **KEEP/INTEGRATE/EXTEND/REPAIR/REPLACE:** **AMBIGUOUS** — needs owner decision on whether this or 1a is the intended Brain going forward.
- **BLOCKERS:** Duplicate-of-purpose with 1a on a different tech stack; not reconciled.

### 1c. my-agent / backtalk (Qwen/Ollama local adapter — distinct from 1a/1b)
- **PATH:** `C:\Users\Arima Finance\my-agent` (submodule `backtalk`)
- **REPOSITORY:** not a git repo in this pass (not checked for `.git`)
- **BUILD/RUNTIME STATUS:** `README-ARYAN-QWEN.md` confirms a local adaptation of `fullstack-agent` for ARIMA Finance, using installed Ollama model `qwen2.5:1.5b-instruct` via `backtalk/qwen_brain.py` (`WarmBrain` class). Launch via `start-aryan-qwen.bat` → face at `http://127.0.0.1:8790/`.
- **RELATION TO AUTHORITATIVE SHEETS:** Not referenced in any prior forensic doc found. Appears to be a separate, lighter-weight local chat front-end, not the Data Fabric Brain.
- **KEEP/INTEGRATE/EXTEND/REPAIR/REPLACE:** **KEEP as-is** (distinct utility, not competing with 1a/1b for the "Brain" role).
- **BLOCKERS:** None identified.

---

## 2. ARIMA World

- **PATH:** `C:\Users\Arima Finance\Documents\Codex\ARIMA-PC-MIGRATION-WORK\ARIMA\aryan-portfolio-local\app\(public)\world-showcase` (+ sibling routes `world-invite`, `world-session`, and `app\(protected)\world`)
- **REPOSITORY:** same repository as §3 (Website) and §4b (ARIMA OS customer frontend) — package name `arima-finance-cinematic` (sha256 of `package.json`: `b7ed8603...bff0b444`)
- **BRANCH:** `main`
- **LAST COMMIT:** `4c92afcd264a90aeac4c1615b982f641adb481be` — 2026-08-28 18:07:23 +0100 — "Add green command center gate transition"
- **WORKING TREE:** dirty — 386 changed/untracked entries
- **BUILD/RUNTIME STATUS:** Not standalone Blender/GLB assets as the discovery brief's search terms implied. It is a WebGL/Three.js product feature built from real components: `components/world/WorldScene.tsx`, `WorldShowcase`, `WorldProduct`, `ConferencePanel.tsx`. GLB/environment assets are present under `public/assets/environment/...` (dozens of files, confirmed present via filesystem search). Prior dev-server evidence (via delegated sub-agent, not independently re-run here) claims 60fps WebGL2 rendering verified on an RTX 4060 — contradicts the prior audit's "inaccessible" classification.
- **TEST STATUS:** Shared with §4b (same repo) — see that section; not independently isolated for World alone.
- **RELATION TO AUTHORITATIVE SHEETS:** `ARIMA_CANONICAL_OWNERSHIP_REPORT.md` classifies this repo path `System: "ARIMA Website / Portfolio"`, `Role: MIGRATION_COPY` — not flagged canonical-original.
- **KEEP/INTEGRATE/EXTEND/REPAIR/REPLACE:** **INTEGRATE** — real working feature, but not cleanly separated from the Website/OS-frontend code in the same repo.
- **BLOCKERS:** Heavily dirty working tree (386 entries); no isolated build/test evidence for World alone, only for the whole app.

---

## 3. Website

- **PATH:** same repository as §2, route group `app\(public)\*`: `intro`, `watch-intro`, `choose-door`, `investment-banking`, `research-projects`, `portfolio-lab`, `work-with-us`, plus `app\(protected)\quant-research`
- **REPOSITORY / BRANCH / LAST COMMIT:** identical to §2 (`aryan-portfolio-local`, branch `main`, commit `4c92afc`)
- **BUILD/RUNTIME STATUS:** `app/layout.tsx` sets `metadataBase: new URL("https://arimafinance.xyz")` — direct, unambiguous confirmation of the production domain. `components/executive/QuantResearchExperience.tsx` and `GrowthStudioExperience.tsx` confirm "Quant Research" / "Growth Studio" exist as implemented sections, not just names in a spec doc. No standalone "Arima Core" or "Q Lab" named component was found under this or any other searched path in this pass — treat as **not found under those exact names** (may be present under different naming, or aspirational/未-implemented).
- **TEST STATUS:** shared with §4b.
- **RELATION TO AUTHORITATIVE SHEETS:** same `MIGRATION_COPY` classification as §2 — this is one repository serving three roles (marketing site, World, and authenticated OS frontend), not three separate systems.
- **KEEP/INTEGRATE/EXTEND/REPAIR/REPLACE:** **INTEGRATE/REPAIR** (see §4b blockers — shared codebase).
- **BLOCKERS:** "Arima Core" / "Q Lab" not located under those names; needs owner clarification on whether these are planned-but-unbuilt or exist under different naming.

---

## 4. ARIMA OS

### 4a. Backend — Arima-Executive-OS (this repository)
- **PATH:** `C:\Users\Arima Finance\Documents\Arima\Arima-Executive-OS` (this report is committed here)
- **REPOSITORY:** `origin = https://github.com/ArimaHQ/Arima-Executive-OS.git`
- **BRANCH:** `feature/laya-intent-engine`
- **LAST COMMIT (at time of this report):** `79a21bd69b46f36828534baf5ec889af4abbc9ac` — 2026-08-26 17:55:02 +0100 — "Merge pull request #5 from ArimaHQ/validation/temp-exact-candidate-scoped-cleanup-20260826"
- **WORKING TREE:** 18 files already staged for an in-progress Laya intent-engine feature (`app/brain/laya_client.py`, `app/core/text.py`, `tests/brain/*`, plus modifications to `app/orchestration/*`, `app/market/instruments.py`, `pyproject.toml`, `requirements.txt`, `.env.example`, and a new Claude skill file). **This report's commit does not touch, stage, or include any of those files.**
- **BUILD/RUNTIME STATUS:** FastAPI app (`pyproject.toml` sha256 `8b11e5462181f8d16595fac79630f2604abc18bc92050b5274bbfed5a998b254`), API prefix `/api/v1`, health routes `/health`, `/health/live`, `/health/ready`. `app.main` import and `pip check` reported passing in a prior bounded audit (not re-run here). Requires PostgreSQL (`asyncpg`, db `arima_executive_os`) — none running locally in this pass. Alembic has 26 migrations plus two duplicate market-price revision files needing a migration-head review.
- **TEST STATUS:** Prior bounded runs: auth/MFA and background test groups passed; full ~560-test suite not claimed fully verified.
- **RELATION TO AUTHORITATIVE SHEETS:** This is the executive/founder-control backend that the mobile/frontend contract docs (`ARIMA_MOBILE_BRAIN_INTEGRATION.md`, etc.) integrate against — the clearest "ARIMA OS" backend candidate found.
- **KEEP/INTEGRATE/EXTEND/REPAIR/REPLACE:** **EXTEND** — active feature branch, functional at source level.
- **BLOCKERS:** No local Postgres instance to verify runtime; 2 duplicate Alembic revision heads; full test suite unverified; on a feature branch with unrelated uncommitted work in progress.

### 4b. Customer web app — aryan-portfolio-local
- **PATH:** `C:\Users\Arima Finance\Documents\Codex\ARIMA-PC-MIGRATION-WORK\ARIMA\aryan-portfolio-local`
- **REPOSITORY / BRANCH / LAST COMMIT:** same as §2/§3 (`main`, `4c92afc`, 386 dirty entries)
- **BUILD/RUNTIME STATUS:** Next.js 16.3.0 / React 19.2.7. 26 page routes + 1 dynamic route, 69 components, 16 API client modules. `app/(protected)/*` = authenticated OS: `dashboard`, `executive`, `growth-studio`, `quant-research`, `admin`, `settings`, `world`, `onboarding`, `withdrawal-request`, `notifications`, `projects`, `tasks`, `founder-grant`. Prior dev-server run (delegated, not re-verified here) reported all routes HTTP 200 on port 3001.
- **TEST STATUS:** TypeScript `tsc --noEmit` PASS. Voice API contract tests 14/14 PASS. Full Vitest suite BLOCKED by a stray macOS AppleDouble artifact (`tests/._voice-api-contract.test.ts`). Two confirmed API contract mismatches: frontend calls `/api/v1/news/latest`, `/api/v1/economic/events`, `/api/v1/portfolio/intelligence`, `/portfolio/history` — none exist on the Executive OS backend router (§4a) — confirmed 404s.
- **RELATION TO AUTHORITATIVE SHEETS:** `MIGRATION_COPY` under "ARIMA Website / Portfolio" per `ARIMA_CANONICAL_OWNERSHIP_REPORT.md`. A sibling, diverged copy also exists (see §6 duplicates table).
- **KEEP/INTEGRATE/EXTEND/REPAIR/REPLACE:** **REPAIR then INTEGRATE.** Prior audit's own explicit verdict: "NOT ready for production."
- **BLOCKERS (priority order, from prior audit):** (1) no approved non-production Executive OS backend + safe test identities to integrate against; (2) onboarding-persistence contract undecided; (3) AppleDouble test artifact blocking full Vitest run; (4) browser-console/multi-viewport/accessibility verification incomplete; (5) the 4 confirmed API contract 404s above must be fixed before backend integration.

### 4c. arima-mobile (third, separate customer-app codebase)
- **PATH:** `C:\Users\Arima Finance\Documents\Codex\ARIMA-FINANCE-CONTROL-CENTER\arima-mobile`
- **REPOSITORY:** **not a git repo** — confirmed no `.git` directory present at this path.
- **BUILD/RUNTIME STATUS:** Expo ~57.0.23, React 19.2.3, React Native 0.86.3. Per its own forensic audit doc (not re-run here): TypeScript PASS, Expo web export PASS, smoke navigation Home→Intelligence→Ask ARIMA→Home rendered. Explicit capability flags all OFF: `LIVE_TRADING=OFF`, `AUTONOMOUS_EXECUTION=OFF`, `MONEY_TRANSFER=OFF`, `WALLET_SIGNING=OFF`, `AI_EXECUTION_AUTHORITY=NONE`.
- **TEST STATUS:** "4 passed, 0 failed" (small, app-scope-only suite).
- **RELATION TO AUTHORITATIVE SHEETS:** A third, much thinner codebase (single `App.tsx`, 4 tests) than 4b (26 routes, 69 components) claiming the same "customer app" role. `ARIMA_MOBILE_API_CONTRACT.md` and related contract docs in the same parent folder describe integration for *this* app but were not cross-checked against 4a's actual router in this pass.
- **KEEP/INTEGRATE/EXTEND/REPAIR/REPLACE:** **REPAIR** (dependency layer) **then EXTEND** — see blockers.
- **BLOCKERS:** Two sibling folders, `arima-mobile-dependency-backup-20260916-192900` and `arima-mobile-dependency-repair-failed-20260916-201500`, record a failed dependency repair attempt dated *after* the last forensic audit in the same folder — the specific failure cause was not isolated (package.json/lockfile diffs and error logs inside those backup folders were not opened in this pass). Native Android/iOS builds not verified on this Windows toolchain. **No document found anywhere that reconciles 4b vs. 4c as the intended canonical customer app** — this is the single largest open ambiguity in this report.

---

## 5. PhoneCam

- **PATH:** `C:\Users\Arima Finance\Documents\Codex\2026-09-21\beb\outputs\PhoneCam`
- **REPOSITORY:** **not a git repo** — no `.git` directory present.
- **BRANCH / LAST COMMIT:** n/a (untracked)
- **BUILD/RUNTIME STATUS:** Real, substantially-built project: Node.js HTTPS signaling server + browser MVP (`app.js`, `server.js`, `index.html`), a per-user DirectShow capture filter ("PhoneCam Camera", CLSID `{58e922b4-27a6-41af-9376-1fb1c04d4a71}`, registered in `HKCU\Software\Classes\CLSID\...`), and a native .NET 10 / SIPSorcery WebRTC receiver under `Native/Receiver`, `Native/DirectShowCamera`, `Native/AudioDriver`, `Native/ThirdParty`. Its own `TEST_REPORT.md` (sha256 `bdad3226...19900f59`, dated 2026-09-21) self-classifies **PARTIAL**: a live iPhone→PC WebRTC session connected (ICE/DTLS/SRTP negotiated; 78,762 video RTP packets and 11,925 encoded VP8 frames received), but the VP8 decoder stalls after ~1,123 decoded frames producing corrupted/banded output; no PCM reaches an actual Windows microphone recording endpoint (none exists — "PhoneCam Microphone" is documented but not installed); the WDK driver toolchain required for a real kernel audio driver fails to install (Visual Studio Installer error 5007).
- **TEST STATUS:** `npm test` 4/4 PASS (app-level only). Hardware/E2E explicitly PARTIAL — see the report's own "Not verified" section (continuous clean decode, non-black DirectShow consumer frames, PCM reaching a real endpoint, no cross-app testing with Meet/Zoom/Teams/OBS/ARIMA, no installer/uninstaller).
- **RELATION TO AUTHORITATIVE SHEETS:** Not mentioned in any `ARIMA-FINANCE-CONTROL-CENTER` forensic document found — entirely outside that prior audit's scope.
- **KEEP/INTEGRATE/EXTEND/REPAIR/REPLACE:** **REPAIR/EXTEND** — signaling and DirectShow plumbing work end-to-end; the media decode pipeline and audio driver do not yet.
- **BLOCKERS:** VP8 decoder instability (~1.5 fps before stalling); no Windows audio recording endpoint/driver; WDK build-tools installation failing (VSInstaller error 5007); untracked by git (no version history / no ownership record).

---

## 6. Duplicate / competing copies (cross-cutting)

| Logical system | Copies found | Canonical per prior audit |
|---|---|---|
| Brain | `Arima-Brain-AUTHORITATIVE` (Node, §1a), `Arima-Brain` (Python, §1b), `my-agent/backtalk` (Qwen adapter, §1c — not competing, different role) | `Arima-Brain-AUTHORITATIVE` rated `NON_CANONICAL_COPY / HIGH` despite its name; `Arima-Brain` not separately rated in the docs read this pass |
| Website/World/OS-frontend | `aryan-portfolio-local` (§2/§3/§4b, live/dirty), `aryan-portfolio` (sibling, branch `main`, commit `c53c650fbc3b7e7ce32f6033ff0c64269b3c7fdb`, 2026-08-21), `overlay-aryan-portfolio`, `overlay-aryan-portfolio-local` (both under `ARIMA-PC-MIGRATION-WORK` root, not opened in this pass) | Both `aryan-portfolio` and `aryan-portfolio-local` rated `MIGRATION_COPY` — **0 repos in this family rated canonical-original by the prior audit** |
| Customer app | `aryan-portfolio-local` (§4b, Next.js), `arima-mobile` (§4c, Expo/RN) | Not reconciled by any document found — open question |
| Website/App backup sets | `BRAIN-CORRECTED-PACKAGE`, `BRAIN-PROVISIONAL-BACKUP-20260910-200328`, `MAC-PACKAGE`, `OS-MAC-COMPARE`, `PC-BACKUP-20260910-192052` (all under `ARIMA-PC-MIGRATION-WORK`) | Not opened/rated in this pass — flagged as unexamined backup/snapshot material |

---

## 7. Canonical-source conclusion

**No system in this discovery has a document-confirmed, undisputed canonical source.** The prior forensic audit already run inside `ARIMA-FINANCE-CONTROL-CENTER` (`ARIMA_CANONICAL_OWNERSHIP_REPORT.md`, 2026-09-16/17) reached the same conclusion independently: 0 of its 12 inventoried repositories were rated `PROVEN_CANONICAL`; only 2 reached `STRONG_CANONICAL_CANDIDATE`; 9 were `NON_CANONICAL`; 4 logical systems had **no** canonical repo at all.

Direct evidence gathered in this pass is consistent with, and does not overturn, that prior conclusion. The practical state of the ARIMA codebase is: the components described as "missing" by the earlier audit are **all physically present and mostly functional**, but scattered across 3-5 same-purpose copies per system with no resolved ownership — an ownership/consolidation problem, not an existence problem.

---

## 8. Unresolved / ambiguous items requiring owner decision

1. Location of `ARIMA_SYSTEM_AUDIT.md` and `ARIMA_EXECUTION_GRAPH.md` (not found locally — §0).
2. Definition/location of "the 3 authoritative ARIMA sheets" (no local match — §0).
3. `Arima-Brain-AUTHORITATIVE` vs. `Arima-Brain` (§1a vs. §1b) — which is the going-forward Brain.
4. `aryan-portfolio-local` vs. `arima-mobile` (§4b vs. §4c) — which is the going-forward customer app; no document reconciles this.
5. `aryan-portfolio` vs. `aryan-portfolio-local` (§6) — which (if either) is canonical for Website/World/OS-frontend.
6. "Arima Core" and "Q Lab" (from the original discovery brief) were not located under those names anywhere searched (§3) — confirm whether these are planned/unbuilt, renamed, or located elsewhere.
7. Contents of the four backup/snapshot folders under `ARIMA-PC-MIGRATION-WORK` (`BRAIN-CORRECTED-PACKAGE`, `BRAIN-PROVISIONAL-BACKUP-20260910-200328`, `MAC-PACKAGE`, `OS-MAC-COMPARE`, `PC-BACKUP-20260910-192052`) were not opened in this pass.

---

*This report preserves discovery/reconciliation evidence only. No application source code, configuration, or existing documents were modified, moved, renamed, or deleted in the course of producing it.*
