import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select

from app.database.models import (
    AIRetrievedContext,
    AuditEntity,
    AuditLog,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSource,
)
from tests.auth.helpers import bearer, csrf_headers, login_user, register_user
from tests.management.conftest import management_context
from tests.voice.test_api import configure_default_voice_agent

__all__ = ["management_context"]

GOLD_NOTE = (
    "Gold rose while real yields increased. Safe-haven demand and central bank "
    "purchases are the leading explanations in the cited report."
)


def _signed_in(context, email: str) -> tuple[dict[str, str], str]:
    register_user(context, email)
    tokens = login_user(context, email)
    headers = bearer(tokens["access_token"])
    me = context.client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    return headers, me.json()["workspace"]["id"]


def _write_headers(context, headers: dict[str, str]) -> dict[str, str]:
    return {**headers, **csrf_headers(context)}


def _source(context, headers, workspace_id: str, **overrides) -> object:
    payload = {
        "source_type": "report",
        "external_id": "gold-report-2026-09",
        "name": "Gold market report",
        "source_uri": "https://example.com/reports/gold",
        **overrides,
    }
    return context.client.post(
        f"/api/v1/knowledge/workspaces/{workspace_id}/sources",
        json=payload,
        headers=_write_headers(context, headers),
    )


def _document(context, headers, workspace_id: str, source_id: str, **overrides) -> object:
    payload = {
        "external_id": "gold-note-1",
        "title": "Gold and real yields",
        "content": GOLD_NOTE,
        "source_observed_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        "provenance": {"source": "example.com", "retrieved_by": "analyst"},
        **overrides,
    }
    return context.client.post(
        f"/api/v1/knowledge/workspaces/{workspace_id}/sources/{source_id}/documents",
        json=payload,
        headers=_write_headers(context, headers),
    )


def _count(context, model, *criteria) -> int:
    async def count() -> int:
        async with context.session_factory() as session:
            return int(await session.scalar(select(func.count(model.id)).where(*criteria)))

    return asyncio.run(count())


def test_member_registers_source_ingests_and_searches_with_provenance(management_context) -> None:
    context = management_context
    headers, workspace_id = _signed_in(context, "knowledge-owner@example.com")

    created = _source(context, headers, workspace_id)
    assert created.status_code == 201
    source = created.json()
    again = _source(context, headers, workspace_id)
    assert again.json()["id"] == source["id"]
    assert source["reliability"] == "unverified"
    assert source["health"] == {
        "document_count": 0,
        "latest_observed_at": None,
        "freshness_state": "no_documents",
        "retrieval_count": 0,
        "last_retrieved_at": None,
    }

    ingested = _document(context, headers, workspace_id, source["id"])
    assert ingested.status_code == 201
    body = ingested.json()
    assert body["duplicate"] is False
    assert len(body["chunk_ids"]) == 1
    assert body["corroborating_source_ids"] == []

    repeat = _document(
        context, headers, workspace_id, source["id"],
        content=GOLD_NOTE.replace(". ", ".  \r\n", 1),
    )
    assert repeat.status_code == 201
    assert repeat.json()["duplicate"] is False  # different normalized text
    same = _document(context, headers, workspace_id, source["id"])
    assert same.json()["duplicate"] is True
    assert same.json()["document_id"] == body["document_id"]

    listing = context.client.get(
        f"/api/v1/knowledge/workspaces/{workspace_id}/sources", headers=headers
    )
    assert listing.status_code == 200
    health = listing.json()[0]["health"]
    assert health["document_count"] == 2
    assert health["freshness_state"] == "not_time_sensitive"

    search = context.client.get(
        f"/api/v1/knowledge/workspaces/{workspace_id}/search",
        params={"q": "why did gold rise with real yields"},
        headers=headers,
    )
    assert search.status_code == 200
    results = search.json()
    assert results and results[0]["source_name"] == "Gold market report"
    assert results[0]["provenance"] == {"source": "example.com", "retrieved_by": "analyst"}
    assert results[0]["reliability"] == "unverified"
    assert 0 < results[0]["score"] <= 1

    assert _count(context, AuditLog, AuditLog.entity == AuditEntity.KNOWLEDGE_SOURCE) == 1
    assert _count(context, AuditLog, AuditLog.entity == AuditEntity.KNOWLEDGE_DOCUMENT) == 2


def test_other_workspaces_cannot_read_or_write_knowledge(management_context) -> None:
    context = management_context
    owner_headers, workspace_id = _signed_in(context, "knowledge-a@example.com")
    source_id = _source(context, owner_headers, workspace_id).json()["id"]
    _document(context, owner_headers, workspace_id, source_id)
    intruder, _ = _signed_in(context, "knowledge-b@example.com")

    assert _source(context, intruder, workspace_id, external_id="x").status_code == 403
    assert _document(context, intruder, workspace_id, source_id, external_id="y").status_code == 403
    assert context.client.get(
        f"/api/v1/knowledge/workspaces/{workspace_id}/sources", headers=intruder
    ).status_code == 403
    search = context.client.get(
        f"/api/v1/knowledge/workspaces/{workspace_id}/search",
        params={"q": "gold"},
        headers=intruder,
    )
    assert search.status_code == 403
    assert GOLD_NOTE not in search.text
    assert _count(context, KnowledgeSource) == 1
    assert _count(context, KnowledgeDocument) == 1


def test_writes_require_csrf_and_authentication(management_context) -> None:
    context = management_context
    headers, workspace_id = _signed_in(context, "knowledge-csrf@example.com")
    no_csrf = context.client.post(
        f"/api/v1/knowledge/workspaces/{workspace_id}/sources",
        json={"source_type": "report", "external_id": "a", "name": "A"},
        headers=headers,
    )
    assert no_csrf.status_code == 403
    anonymous = context.client.get(f"/api/v1/knowledge/workspaces/{workspace_id}/sources")
    assert anonymous.status_code == 401
    assert _count(context, KnowledgeSource) == 0


def test_invalid_provenance_credentials_and_timestamps_are_rejected(management_context) -> None:
    context = management_context
    headers, workspace_id = _signed_in(context, "knowledge-validate@example.com")
    leaked = _source(
        context, headers, workspace_id, source_uri="https://example.com/feed?api_key=abc"
    )
    assert leaked.status_code == 422
    source_id = _source(context, headers, workspace_id).json()["id"]

    assert _document(context, headers, workspace_id, source_id, provenance={}).status_code == 422
    assert _document(
        context, headers, workspace_id, source_id, provenance={"source": "x", "token": "t"}
    ).status_code == 422
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert _document(
        context, headers, workspace_id, source_id, source_observed_at=future
    ).status_code == 422
    assert _document(
        context, headers, workspace_id, source_id, content=" \r\n\x00 "
    ).status_code == 422
    assert _count(context, KnowledgeDocument) == 0


def test_only_founder_control_may_declare_official_sources(management_context) -> None:
    context = management_context
    headers, workspace_id = _signed_in(context, "knowledge-client@example.com")
    response = _source(context, headers, workspace_id, reliability="official")
    assert response.status_code == 403
    assert _count(context, KnowledgeSource) == 0
    primary = _source(
        context, headers, workspace_id, reliability="primary", authority="Company filing"
    )
    assert primary.status_code == 201
    assert primary.json()["reliability"] == "primary"
    assert primary.json()["authority"] == "Company filing"


def test_corroboration_and_reliability_order_results_without_admitting_stale(management_context) -> None:
    context = management_context
    headers, workspace_id = _signed_in(context, "knowledge-rank@example.com")
    weak = _source(context, headers, workspace_id, external_id="blog", name="Blog").json()
    strong = _source(
        context, headers, workspace_id, external_id="filing", name="Filing",
        reliability="primary",
    ).json()
    stale = _source(
        context, headers, workspace_id, external_id="wire", name="Wire",
        reliability="primary", freshness_required=True, max_age_seconds=60,
    ).json()

    _document(context, headers, workspace_id, weak["id"])
    corroborated = _document(context, headers, workspace_id, strong["id"])
    assert corroborated.json()["corroborating_source_ids"] == [weak["id"]]
    _document(
        context, headers, workspace_id, stale["id"], external_id="old",
        content=GOLD_NOTE + " Wire copy.",
        source_observed_at=(datetime.now(UTC) - timedelta(hours=2)).isoformat(),
    )

    results = context.client.get(
        f"/api/v1/knowledge/workspaces/{workspace_id}/search",
        params={"q": "gold real yields safe-haven"},
        headers=headers,
    ).json()
    assert [item["source_name"] for item in results] == ["Filing", "Blog"]
    assert all(item["corroborating_source_count"] == 1 for item in results)
    assert results[0]["score"] > results[1]["score"]
    states = {
        item["name"]: item["health"]["freshness_state"]
        for item in context.client.get(
            f"/api/v1/knowledge/workspaces/{workspace_id}/sources", headers=headers
        ).json()
    }
    assert states == {"Blog": "not_time_sensitive", "Filing": "not_time_sensitive", "Wire": "stale"}


def test_ingested_knowledge_reaches_the_brain_as_run_evidence(management_context) -> None:
    context = management_context
    email = "knowledge-brain@example.com"
    headers, workspace_id = _signed_in(context, email)
    configure_default_voice_agent(context, email, grant=True)
    source_id = _source(context, headers, workspace_id).json()["id"]
    ingested = _document(context, headers, workspace_id, source_id).json()

    session = context.client.post("/api/v1/voice/sessions", json={}, headers=headers)
    assert session.status_code == 201
    answer = context.client.post(
        f"/api/v1/voice/sessions/{session.json()['session_id']}/transcript",
        json={"transcript": "Why did gold rise while real yields increased?"},
        headers=headers,
    )
    assert answer.status_code == 200
    # The deterministic mock provider echoes its payload: the ingested text
    # reached the Brain prompt stamped with its observation date.
    echoed = answer.json()["response_text"]
    assert "[observed " in echoed and "Safe-haven demand" in echoed

    async def evidence_chunks() -> set[str]:
        async with context.session_factory() as db:
            rows = await db.scalars(
                select(KnowledgeChunk.document_id)
                .join(AIRetrievedContext, AIRetrievedContext.chunk_id == KnowledgeChunk.id)
                .where(AIRetrievedContext.workspace_id == UUID(workspace_id))
            )
            return {str(value) for value in rows.all()}

    assert ingested["document_id"] in asyncio.run(evidence_chunks())
    health = context.client.get(
        f"/api/v1/knowledge/workspaces/{workspace_id}/sources", headers=headers
    ).json()[0]["health"]
    assert health["retrieval_count"] >= 1
