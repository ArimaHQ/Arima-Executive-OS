# Phase 4 governed intelligence foundation

Phase 4 extends the existing provider, agent, orchestration, tool, memory, and
voice foundations. It does not add a second AI stack or a customer-facing
market-data surface.

## Durable ownership and audit chain

Every governed workflow binds an existing `agent_runs` row to one workspace
and one verified Arima user in `ai_workspace_runs`. An explicit active
`workspace_agent_grants` row is required before the agent can run. The binding
is immutable and complements the existing conversation owner and run trigger
checks.

The durable chain is:

`user -> workspace -> conversation -> agent -> run -> retrieved context -> tool executions -> output`

`AuditChainService` reconstructs that chain only after checking the requesting
user's exact workspace membership and run ownership.

## Knowledge and retrieval

Approved inputs are normalized into workspace-owned sources, versioned
documents, and deterministic chunks. Documents require source provenance and
timezone-aware observation timestamps. Freshness-required sources require a
maximum age. Retrieval scopes every joined table to the same workspace,
rejects missing run ownership, skips stale or provenance-less records, and
persists every returned chunk as `ai_retrieved_contexts` evidence.

Provider credentials are not valid provenance and credential-bearing source
URIs are rejected.

## Executive workflows

`ExecutiveWorkflowService` creates the existing durable conversation, user
message, and agent run records; binds the run to its workspace; records
retrieval evidence; invokes the existing orchestration engine; stores the
assistant output; and completes or fails the run durably. Tool authorization,
approvals, and execution auditing remain owned by the existing orchestration
and tool layers.

## Telegram transport

Telegram is disabled by default. Its webhook accepts Telegram's standard
secret-token header and message update shape. The transport requires both a
server-side webhook secret and a verified
mapping from the Telegram user/chat pair to an active, verified Arima user and
workspace membership. Telegram identity is never sufficient authorization by
itself. The normal agent and workspace checks still run.

Accepted updates persist incoming text, response text, Telegram update/chat
and message identifiers, timestamps, processing status, errors, conversation,
run, user, workspace, and identity. Telegram update IDs are unique, making
replays idempotent. Bot and webhook credentials use secret settings and are
never persisted in these records or returned to clients.

## Knowledge API (Layer 1 entry point)

`/api/v1/knowledge/workspaces/{workspace_id}/...` is the only way content
enters the knowledge store the Brain retrieves from:

- `POST sources`, `GET sources`: register and list sources. Listings include
  health derived from stored rows: document count, latest observation,
  freshness state, and how often the Brain retrieved each source.
- `POST sources/{source_id}/documents`: ingest one document.
- `GET search?q=`: read-only memory search. It applies the same tenancy,
  provenance and staleness filters as Brain retrieval and records no run
  evidence.

Every call requires workspace membership. Writes also require CSRF, and new
sources and documents are audited. Each source declares a reliability tier
(`official`, `primary`, `established`, `user_provided`, `unverified`). Only
Founder Control may declare `official`. Tier and cross-source corroboration
change the ranking order only; they never let in evidence that failed the
provenance, freshness or tenancy filters. Content is normalized before
hashing, so re-sent text is reported as a duplicate and not re-chunked.

The voice Brain path now retrieves research that is not time-sensitive, and
stamps each evidence item with its observation date. Stale and expired
evidence is still excluded.

## Exposure boundary

Knowledge endpoints are the only client-facing Phase 4 additions besides the
Telegram webhook. The webhook is server-authenticated,
resolves an exact workspace from a verified identity, re-runs normal Arima
authorization, and exposes no orchestration internals. No customer price,
quote, or time-series endpoint is added. Phase 2 and Phase 3.1 market
availability and fail-closed licensing behavior remain unchanged.
