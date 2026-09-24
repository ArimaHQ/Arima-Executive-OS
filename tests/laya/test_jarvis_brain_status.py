from datetime import UTC, datetime, timedelta

from tests.auth.helpers import csrf_headers
from tests.intelligence.test_knowledge_api import _document, _signed_in, _source
from tests.laya.test_laya import founder
from tests.management.conftest import management_context
from tests.voice.test_api import configure_default_voice_agent

__all__ = ["founder", "management_context"]
STATUS = "/api/v1/admin/founder/brain/status"


def test_brain_status_is_founder_only(management_context, founder) -> None:
    context = management_context
    client, _ = _signed_in(context, "jarvis-client@example.com")
    assert context.client.get(STATUS, headers=client).status_code == 403
    assert context.client.get("/api/v1/admin/founder/execution-policy", headers=client).status_code == 403
    assert context.client.get(STATUS).status_code == 401
    policy = context.client.get("/api/v1/admin/founder/execution-policy", headers=founder)
    assert policy.json() == {
        "execution_authority": "NONE",
        "live_execution": False,
        "autonomous_execution": False,
        "paper_execution": True,
        "external_execution": "DISCONNECTED",
    }


def test_brain_status_reflects_real_state_without_tenant_content(management_context, founder) -> None:
    context = management_context
    empty = context.client.get(STATUS, headers=founder).json()
    codes = {gap["code"] for gap in empty["gaps"]}
    assert "agent_platform_not_bootstrapped" in codes
    assert "no_official_sources" in codes
    assert empty["knowledge"]["documents"] == 0
    assert empty["execution_policy"]["execution_authority"] == "NONE"

    email = "jarvis-owner@example.com"
    headers, workspace_id = _signed_in(context, email)
    configure_default_voice_agent(context, email, grant=True)
    source = _source(
        context, headers, workspace_id, external_id="wire", name="Private client wire",
        freshness_required=True, max_age_seconds=60,
    ).json()
    _document(
        context, headers, workspace_id, source["id"],
        source_observed_at=(datetime.now(UTC) - timedelta(hours=1)).isoformat(),
    )

    status = context.client.get(STATUS, headers=founder)
    assert status.status_code == 200
    body = status.json()
    assert body["agents"]["default_agent"] == "executive-assistant"
    assert body["agents"]["default_agent_active"] is True
    assert body["knowledge"]["documents"] == 1
    assert body["knowledge"]["sources_by_reliability"]["unverified"] == 1
    assert body["knowledge"]["stale_time_sensitive_sources"] == 1
    assert body["providers"]["default_provider"] == "mock"
    assert body["news_provider"] == "not_configured"
    codes = {gap["code"] for gap in body["gaps"]}
    assert "stale_time_sensitive_sources" in codes
    assert "agent_platform_not_bootstrapped" not in codes
    assert "Private client wire" not in status.text
    assert "Gold rose" not in status.text


def test_jarvis_hands_gaps_to_laya_not_to_execution(management_context, founder) -> None:
    context = management_context
    created = context.client.post(
        "/api/v1/admin/founder/brain/gaps/no_official_sources/task",
        headers={**founder, **csrf_headers(context)},
    )
    assert created.status_code == 201
    task = created.json()
    assert task["key"] == "GAP-no_official_sources"
    assert task["status"] == "discovered"
    assert task["acceptance_criteria"] == ["Brain status no longer reports gap no_official_sources"]

    duplicate = context.client.post(
        "/api/v1/admin/founder/brain/gaps/no_official_sources/task",
        headers={**founder, **csrf_headers(context)},
    )
    assert duplicate.status_code == 409
    unknown = context.client.post(
        "/api/v1/admin/founder/brain/gaps/not_a_gap/task",
        headers={**founder, **csrf_headers(context)},
    )
    assert unknown.status_code == 404
    graph = context.client.get("/api/v1/admin/founder/laya/graph", headers=founder).json()
    assert graph["counts"]["discovered"] == 1
