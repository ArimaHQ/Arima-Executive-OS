---
name: arima-laya-intelligence
description: >
  Engineering skill for integrating, operating, testing, and extending Laya
  multilingual intelligence inside ARIMA. Use this skill whenever a task
  involves Laya, laya-serve, multilingual intent understanding, IntentEngine,
  natural-language routing, intent classification, orchestration, confidence
  thresholds, fallback routing, or Laya-related tests and observability.
---

# ARIMA Laya Intelligence Skill

## 1. Purpose

This skill defines how Claude Code must design, implement, test, debug, and
extend Laya intelligence inside the ARIMA system.

Laya is an intelligence augmentation layer, not a replacement for ARIMA's
deterministic safety, routing, orchestration, financial controls, or execution
controls.

The objective is to provide stronger multilingual and natural-language intent
understanding while preserving:

- deterministic behavior where deterministic behavior is required;
- existing ARIMA routing contracts;
- fail-safe behavior;
- backward compatibility;
- observability;
- tenant/workspace isolation;
- testability;
- production safety;
- zero live-execution authority.

Never treat Laya being available as a reason to weaken an existing safety or
control boundary.

## 2. When This Skill MUST Be Used

Use this skill before making changes involving any of the following:

- `laya-serve`
- Laya model/runtime configuration
- Laya HTTP/API integration
- multilingual intent classification
- Persian-language intent understanding
- `IntentEngine`
- orchestration routing
- natural-language routing
- confidence thresholds
- intent fallback logic
- Laya timeout behavior
- Laya availability/recovery
- `intent_source`
- Laya observability
- Laya tests
- intent regression tests
- multilingual routing failures
- Laya performance
- Laya model changes
- Laya deployment/configuration
- changes that cause natural-language requests to select ARIMA tools

If uncertain whether a task touches Laya intelligence, inspect the current
architecture and use this skill rather than assuming.

## 3. Core Architectural Principle

The canonical intent resolution hierarchy is:

1. Explicit intent supplied by the caller.
2. Deterministic ARIMA rules that are intentionally authoritative.
3. Laya classification, when enabled and healthy.
4. Existing deterministic keyword/rule fallback.
5. Safe unresolved/unknown result when no reliable intent can be established.

Laya MUST NOT blindly replace deterministic routing.

```text
Request
   |
   v
Explicit intent?
   | yes
   +--------------------> use explicit intent
   |
   no
   v
Authoritative deterministic route?
   | yes
   +--------------------> use deterministic route
   |
   no
   v
Laya enabled + available?
   | no
   +--------------------> keyword/rule fallback
   |
   yes
   v
Laya classification
   |
   +-- confidence >= threshold --> use Laya intent
   |
   +-- confidence < threshold --> fallback
   |
   +-- timeout/error/malformed --> fallback
```

This hierarchy may only be changed deliberately, with regression tests and
explicit architectural justification.

## 4. Laya Is Advisory Intelligence

Laya is advisory with respect to intent. Laya MUST NOT directly:

- execute trades;
- submit orders;
- move capital;
- withdraw funds;
- transfer assets;
- modify execution authority;
- enable live execution;
- bypass approval workflows;
- bypass Founder Control Center protections;
- bypass authentication;
- bypass authorization;
- modify tenant/workspace isolation;
- directly mutate financial positions;
- disable audit logging;
- override deterministic safety controls.

A Laya classification may select an allowed application route. The selected
route remains responsible for its own authentication, authorization,
validation, safety checks, business rules, execution controls, and
auditability.

Never assume:

```text
Laya says "trade"
=> trading is authorized
```

Instead:

```text
Laya intent
=> application route
=> authorization
=> policy validation
=> execution controls
=> allowed action or refusal
```

## 5. Current ARIMA Safety Baseline

Unless explicitly changed and independently verified, preserve:

```text
executionAuthority = NONE
liveExecution = false
autonomousExecution = false
paperExecution = true
externalExecution = DISCONNECTED
```

Laya integration must not alter this posture. If a proposed Laya change would
alter any of these values, STOP and treat the change as a protected
architectural boundary.

Do not "temporarily" enable execution for testing. Use mocks, fakes, fixtures,
paper execution, or isolated test adapters.

## 6. Existing Laya Integration Contract

The current integration is designed around an asynchronous HTTP client.
Expected conceptual components:

```text
app/brain/laya_client.py
app/orchestration/router.py
```

Do not assume these paths are permanently canonical. Before editing:

1. inspect the repository;
2. locate the actual implementation;
3. inspect tests;
4. inspect configuration;
5. inspect callers;
6. confirm the current branch state.

Never recreate an existing component because a path from this document is
slightly outdated.

## 7. Laya Client Requirements

The Laya client should be asynchronous, HTTP-based, timeout-bounded,
configuration-driven, non-fatal, observable, testable with a fake server, and
safe when Laya is unavailable.

The client MUST NOT turn Laya failure into an application-wide failure.

```text
Laya healthy               -> return validated classification
Laya unavailable           -> return no classification
Laya timeout               -> return no classification
Laya malformed response    -> return no classification
Laya low confidence        -> return no classification
Laya unexpected exception  -> return no classification
```

The caller then performs the deterministic fallback. Do not silently fabricate
an intent when Laya fails.

## 8. Configuration

Current configuration concepts:

```text
LAYA_URL
LAYA_API_KEY
LAYA_TIMEOUT_SECONDS
LAYA_MIN_CONFIDENCE
```

These values must remain configuration-driven. Laya should be off by default
unless the repository's current production configuration explicitly
establishes another policy. Default-off preserves existing production behavior
when Laya infrastructure is unavailable.

When adding new Laya configuration: document it; provide safe defaults; update
`.env.example` where appropriate; add tests; avoid hard-coded credentials;
never commit secrets; never print API keys in logs.

## 9. Confidence Handling

A Laya classification is usable only when its confidence satisfies the
configured minimum threshold:

```python
if result.intent and result.confidence >= LAYA_MIN_CONFIDENCE:
    return result
return None
```

Do not invent confidence values. Do not reinterpret a malformed confidence as
high confidence. Reject: missing confidence; non-numeric confidence; NaN;
infinity; out-of-range values; malformed response structures.

The exact valid range must follow the current Laya API contract. If unclear,
inspect the implementation/tests before changing behavior.

## 10. Intent Source Observability

Every resolved intent should preserve the source of the decision where the
architecture supports it. Conceptual values:

```text
explicit | deterministic | laya | keyword | fallback | unknown
```

Use the repository's existing enum/string contract if one exists; do not
introduce competing representations. Observability must answer: *why did
ARIMA choose this intent?*

```text
intent = market.current_price
intent_source = laya
confidence = 0.94
```

Do not log: API keys; credentials; secrets; private financial information;
unnecessary full prompts; authentication tokens.

## 11. Multilingual Behavior

Support multilingual requests without making language detection a new unsafe
routing mechanism. Important cases: Persian; English; mixed Persian/English;
financial terminology; ticker symbols; abbreviations; colloquial wording;
transliterated Persian (Finglish); multilingual financial questions.

Do not normalize away meaningful financial identifiers
(`WTI XAU BTC EURUSD VIX SPX Nasdaq Brent` …). Preserve ticker and instrument
identity.

## 12. Persian Language Handling

Persian requests are first-class inputs. Do not assume
`Persian = keyword translation`. Laya may understand semantic intent when
configured, but deterministic financial identifiers and explicit application
commands stay protected from unnecessary Laya interpretation. If an existing
deterministic route reliably identifies an explicit market-data command,
preserve it. Test mixed-language requests too.

## 13. Curly Apostrophe and Unicode Robustness

Routing must handle Unicode variants, e.g. `What's WTI...` vs `What’s WTI...`.
Do not solve this with one isolated special case if a general normalization
layer is appropriate. Before fixing:

1. reproduce the failure;
2. inspect normalization behavior;
3. decide whether it belongs in preprocessing, matching, or routing;
4. add regression tests;
5. verify existing routes remain unchanged.

Avoid destructive normalization that changes financial identifiers.

## 14. Fallback Requirements

Fallback is a first-class feature, not an error condition, and the chain must
stay deterministic. Timeout / unavailable / malformed / low confidence →
deterministic fallback.

Never `Laya failure -> random intent`. Never `Laya timeout -> block the
application indefinitely`. Never make the application depend on Laya
availability unless separately approved.

## 15. Timeout Requirements

Laya must have a finite, configuration-driven timeout. On timeout: stop
waiting, record observability, return no classification, continue with
fallback. Do not raise the timeout indefinitely to make Laya look more
accurate — latency is part of the contract.

## 16. Error Handling

Isolate Laya errors. Handle at minimum: connection errors; DNS/network errors;
HTTP errors; timeout; invalid JSON; missing fields; malformed schema; invalid
confidence; unknown intent; model/service unavailable; unexpected client
exceptions.

Avoid broad exception handling that hides unrelated programming errors — keep
handling narrow around the external Laya boundary.

## 17. Testing Strategy

**Unit tests:** valid response; invalid response; low/high confidence;
timeout; service unavailable; HTTP failure; malformed JSON; missing fields;
explicit-intent precedence; deterministic-route precedence; keyword fallback;
multilingual, Persian, mixed-language requests; Unicode punctuation;
`intent_source`.

**Integration tests:** use a fake/local Laya server and verify
`request -> IntentEngine -> Laya client -> response -> confidence validation
-> selected intent -> orchestration route`.

**Regression tests:** every discovered routing bug becomes a regression test.
Fix the general bug, not just the observed string.

## 18. Test Environment Discipline

Development/testing runs on Windows (CPU-only). Distinguish
Windows-infrastructure issues from product failures. If tests are slow:
determine whether they actually hang; get a stack trace; identify
filesystem/database/network bottlenecks; benchmark; fix test-only performance
problems without modifying production behavior. Do not call a test deadlocked
just because it takes minutes.

SQLite test configuration may use an optimized journal mode for tests;
production database behavior stays untouched unless the task targets it.

## 19. Dependency Discipline

When a test needs a missing dependency: decide production vs dev-only;
inspect existing dependency management; add to the correct group; document
why; rerun the relevant tests, then the full suite. Never install packages
globally and call the test fixed. Known dev requirements may include
`pytest-asyncio`, `pytest-timeout`, `tzdata` — verify current dependency files
first.

## 20. Real Laya Verification

Fake-server tests do not prove the real runtime works. When infrastructure is
available, verify: laya-serve starts → health/reachability → model loads →
request accepted → valid classification → IntentEngine consumes result →
correct intent selected → fallback still works when Laya is stopped.

This must never require live trading or external execution. If a model
download is required, document model identity, size, hardware, runtime,
latency, memory, and limitations. Do not silently download large models or
change the machine globally without authorization.

## 21. Laya Performance

Measure, don't guess: latency; timeout rate; fallback rate; success rate;
low-confidence rate; malformed-response rate; agreement with deterministic
routing; memory. Do not trade application availability for accuracy — a slow
model that constantly falls back may add no value.

## 22. Model Changes

When changing the model: identify current; document proposed; test
representative intents, multilingual inputs, financial identifiers,
low-confidence and failure behavior; compare latency; run regression tests.
Do not swap models just because a newer one exists — the model is part of the
system contract.

## 23. Prompt / Response Contracts

Validate structured output at the boundary. Conceptual schema
`{ intent: string, confidence: number }`; the actual schema follows the
current implementation. Model output is data. Never execute model-generated
shell commands, SQL, Python, JavaScript, filesystem operations, network
requests, or financial instructions.

## 24. Security

Treat Laya as an external, untrusted boundary: never trust model output,
external HTTP responses, or model-generated URLs/commands/SQL/paths. Validate
everything. Never expose `LAYA_API_KEY` in logs, client-facing exceptions,
screenshots, fixtures, commits, or docs. Use fake credentials in tests.

## 25. Tenant and Workspace Isolation

Requests keep their tenant, workspace, user, authorization, and audit context.
No global Laya state that mixes users/workspaces. Any cache key must include
the isolation boundary. Never share user-specific intelligence across tenants.

## 26. Caching

Optional and must be justified. First determine whether the request is
user-specific, workspace-specific, time-sensitive, or market-sensitive. Never
let cached market-sensitive results appear current; never build a global
semantic cache that leaks private context.

## 27. Changes to Intent Taxonomy

When adding an intent: define it; identify its owning route; identify
authorization requirements; define fallback; add unit, integration, and
multilingual tests; add observability; verify no existing intent becomes
ambiguous. No aliases routing to different tools unless the distinction is
explicit and testable.

## 28. Deterministic Financial Routing

Do not let semantic classification turn one instrument into another
(`WTI Brent XAU XAG BTC ETH EURUSD SPX NDX VIX`). For market-data requests,
preserve instrument identity, operation, time horizon, units, and market
context. If Laya is uncertain, deterministic routing or unresolved is better
than a fabricated financial interpretation.

## 29. No Hallucinated Intent

If no sufficiently reliable intent can be established, `unknown / unresolved`
beats an incorrect confident route — especially for financial requests.

## 30. Observability and Audit

Where supported, record `intent`, `intent_source`, `confidence`, `latency`,
`fallback_used`, `laya_status`. Store no more user content than necessary.
Do not weaken existing audit controls or trails for sensitive workflows.

## 31. Failure Recovery

A Laya outage must be recoverable without restarting unrelated services.
Laya DOWN → ARIMA stays operational with deterministic routing. Laya UP →
classification resumes. Avoid persistent "Laya unavailable" state unless it is
explicitly designed, observable, and recoverable.

## 32. Autonomous Engineering Workflow

1. **Inspect** — repo structure, branch, implementation, config, tests,
   dependencies, architecture docs. Do not edit immediately.
2. **Establish baseline** — run the smallest relevant tests; record passing,
   failing, environment, and pre-existing failures.
3. **Implement minimally** — smallest architecture-consistent change; no
   unrelated refactors.
4. **Add tests** — every new behavior.
5. **Run focused tests** — fix implementation failures.
6. **Run regression suite** — separate pre-existing from new failures; new
   tests passing is not success.
7. **Integration verification** — the complete request path.
8. **Real-runtime verification** — against actual Laya when available.
9. **Security/safety review** — no execution authority or protected boundary
   changed.
10. **Final classification** — only `COMPLETE`, `PARTIAL`, or `BLOCKED`. Not
    COMPLETE while real verification is missing.

## 33. Definition of Done

COMPLETE only when all applicable items hold:

- **Code:** client, IntentEngine integration, configuration, fallback,
  observability.
- **Tests:** Laya unit, intent routing, fallback, timeout/error,
  multilingual, regression, and relevant full suite pass.
- **Runtime:** runtime starts, model loads, real request succeeds,
  IntentEngine consumes real result, failure falls back.
- **Safety:** no live execution, no execution-authority change, no
  authn/authz bypass, no isolation regression, no secrets exposed.
- **Documentation:** configuration, runtime requirements, known limitations,
  test requirements.
- **Verification:** no unresolved new failures; pre-existing failures listed
  separately; evidence reproducible.

Any required item unverified → `PARTIAL`.

## 34. Commit Discipline

Before committing: inspect git status and diff; verify changed files; ensure
no secrets or generated artifacts; run relevant tests; confirm no unrelated
modifications. Use a focused message. Do not push unless explicitly
authorized. If asked whether to commit, report verification state first.

## 35. Do Not Overwrite Existing Architecture

Before replacing a component, establish why, what depends on it, what tests
protect it, and whether a smaller extension suffices. Prefer extend over
rewrite.

## 36. Do Not Create Fake Completeness

Compiling, passing unit tests, a working fake server, existing config, or a
theoretically runnable model do not make Laya complete. Distinguish
*implemented* → *tested* → *integrated* → *real-runtime verified* →
*production verified*.

## 37. Interaction With the Three-Sheet ARIMA Roadmap

This skill is a specialized rule set inside the broader three-sheet
architecture; do not reduce that architecture to Laya. When a requirement
touches Brain, Intelligence, orchestration, research, market intelligence,
customer-facing intelligence, agent coordination, or financial reasoning,
decide whether Laya is relevant before implementing. Don't force Laya where
deterministic logic fits better.

## 38. Relationship to ARIMA Brain

Laya contributes natural-language understanding inside the Brain ecosystem
(alongside deterministic systems, research/evidence, intelligence,
orchestration, agents, safety/governance). It is a capability, not the
authority over the Brain.

## 39. Relationship to Agents

Laya may classify intent before an agent workflow is selected, but an agent
selected via Laya still operates within agent permissions, workspace grants,
authn/authz, safety policy, and audit requirements. Never use Laya output to
grant privileges.

## 40. Relationship to Financial Intelligence

Laya understands what the user asks; market/data/research systems establish
facts; financial intelligence reasons over evidence; the application presents
results. Laya is not a source of financial truth.

## 41. Relationship to Research and Evidence

Intent classification is not evidence retrieval. Laya may identify that a
user wants current WTI information; it does not establish the WTI price.

## 42. User Experience

Keep routing explainable to developers. Don't expose internal confidence to
end users unless the product design calls for it. Use factual language — never
claim Laya "understood perfectly."

## 43. Debugging Checklist

Incorrect routing:

```text
[ ] Reproduce exact input
[ ] Preserve exact Unicode
[ ] Identify expected intent
[ ] Identify actual intent
[ ] Check explicit intent
[ ] Check deterministic rules
[ ] Check normalization
[ ] Check Laya request
[ ] Check Laya response
[ ] Check confidence
[ ] Check threshold
[ ] Check fallback
[ ] Check final router
[ ] Add regression test
```

Laya appears broken:

```text
[ ] Is Laya enabled?
[ ] Is LAYA_URL correct?
[ ] Is the service reachable?
[ ] Is the model loaded?
[ ] Is timeout sufficient?
[ ] Is the response schema valid?
[ ] Is confidence valid?
[ ] Is the request reaching IntentEngine?
[ ] Is fallback masking the result?
[ ] Is the failure actually pre-existing?
```

## 44. Final Engineering Rule

The objective is not "make Laya work." It is: make Laya a reliable,
observable, bounded intelligence capability inside ARIMA without weakening
deterministic behavior, safety, evidence integrity, isolation, or execution
controls.

When in doubt:

```text
Preserve safety.
Preserve deterministic fallback.
Preserve existing contracts.
Measure before changing.
Test before claiming.
Verify before marking COMPLETE.
```
