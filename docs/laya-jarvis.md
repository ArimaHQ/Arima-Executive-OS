# Laya and Jarvis (founder orchestration)

Both surfaces are Founder Control only. A caller needs an allowlisted,
verified administrator and, in production, an enrolled privileged MFA
factor. Clients never reach them.

## Jarvis: `/api/v1/admin/founder/brain/*`

- `GET brain/status` returns one view over the single Brain:
  - the locked execution policy;
  - the default agent and how many workspaces hold its grant;
  - the configured LLM provider and its health;
  - knowledge aggregates by reliability tier, stale time-sensitive sources,
    and retrievals in the last 24 hours;
  - market provider configuration;
  - the Laya summary;
  - a list of **gaps** derived from that same state.

  It returns aggregates only: no tenant names, titles, or content.
- `GET execution-policy` returns the immutable posture: `NONE / false / false
  / true / DISCONNECTED`.
- `POST brain/gaps/{code}/task` hands a currently reported gap to Laya as a
  task. Jarvis never acts on a gap directly.

## Laya: `/api/v1/admin/founder/laya/*`

A persisted task graph. Every task records its key, purpose, owner,
dependencies, inputs/outputs, systems, acceptance criteria, tests, evidence,
blockers and status. The statuses are `discovered, ready, running, blocked,
failed, retry, verifying, passed, completed, rejected`.

Enforced invariants:

- A task cannot run, verify, pass or complete while a dependency is below
  `passed`.
- `passed` needs `test` evidence. `completed` also needs `e2e` or
  `production_verification` evidence, plus acceptance criteria.
- A failure must be classified, and the class sets the recovery:

  | Class | Outcome |
  |---|---|
  | transient | retry until attempts run out, then escalate |
  | data, code | repair |
  | dependency | blocked |
  | permission, infrastructure, architectural | blocked and escalated to a human |

- A dependency that regresses blocks its dependents that are still in
  progress.
- Cycles, self-dependencies and duplicate keys are rejected. Every mutation
  is audited.

`reports/laya_task_graph.json` is the machine-readable execution graph.
`scripts/load_laya_graph.py` drives it through Laya's real transitions, so
a claimed status holds only if Laya accepts the evidence and dependencies.
