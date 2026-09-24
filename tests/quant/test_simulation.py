from dataclasses import asdict

import pytest

from app.quant.simulation import (
    MAX_WORK,
    MIN_SIMULATIONS,
    SimulationInputError,
    run_monte_carlo,
)
from tests.management.conftest import management_context

__all__ = ["management_context"]

# Golden summaries produced by running Arima Finance Engine v3
# (modules/monte_carlo_analytics.py @ dc6e1d7) on the same inputs and seeds.
V3_MIXED = {
    "simulations": 10000, "trades_per_simulation": 12, "initial_equity": 1000.0,
    "probability_of_profit": 68.93, "probability_of_loss": 31.06,
    "probability_of_new_equity_high": 54.76, "probability_of_ruin": 0.0,
    "expected_final_equity": 1166.402525, "median_final_equity": 1159.75,
    "best_final_equity": 2451.0, "worst_final_equity": 133.5,
    "maximum_simulated_drawdown": 866.5, "average_simulated_drawdown": 236.1653,
    "confidence_interval_95": (565.0, 1813.5125),
    "confidence_interval_99": (404.495, 2021.00625),
}
V3_RUINOUS = {
    "simulations": 10000, "trades_per_simulation": 4, "initial_equity": 500.0,
    "probability_of_profit": 19.08, "probability_of_loss": 74.67,
    "probability_of_new_equity_high": 52.74, "probability_of_ruin": 55.44,
    "expected_final_equity": 52.615, "median_final_equity": 50.0,
    "best_final_equity": 1100.0, "worst_final_equity": -1100.0,
    "maximum_simulated_drawdown": 1600.0, "average_simulated_drawdown": 652.075,
    "confidence_interval_95": (-900.0, 1000.0),
    "confidence_interval_99": (-1000.0, 1050.0),
}
MIXED = [120.0, -80.0, 45.5, -60.0, 210.0, -95.25, 30.0, -40.0, 75.0, -110.0, 55.0, 18.75]


def _without_provenance(summary) -> dict:
    values = asdict(summary)
    values.pop("seed")
    values.pop("input_sha256")
    return values


@pytest.mark.parametrize(
    ("profits", "equity", "seed", "expected"),
    [
        (MIXED, 1_000.0, 0, V3_MIXED),
        ([-400.0, 150.0, -300.0, 100.0], 500.0, 7, V3_RUINOUS),
    ],
)
def test_port_matches_finance_engine_v3(profits, equity, seed, expected) -> None:
    summary = run_monte_carlo(profits, initial_equity=equity, seed=seed)
    assert _without_provenance(summary) == expected


def test_same_input_and_seed_is_reproducible_with_provenance() -> None:
    first = run_monte_carlo(MIXED, initial_equity=1_000.0, seed=3)
    second = run_monte_carlo(MIXED, initial_equity=1_000.0, seed=3)
    other_seed = run_monte_carlo(MIXED, initial_equity=1_000.0, seed=4)
    assert first == second
    assert first.seed == 3 and len(first.input_sha256) == 64
    assert other_seed.input_sha256 == first.input_sha256
    assert other_seed.expected_final_equity != first.expected_final_equity


@pytest.mark.parametrize(
    ("profits", "equity", "simulations"),
    [
        ([], 1_000.0, MIN_SIMULATIONS),
        ([float("nan")], 1_000.0, MIN_SIMULATIONS),
        ([float("inf")], 1_000.0, MIN_SIMULATIONS),
        ([10.0], 0.0, MIN_SIMULATIONS),
        ([10.0], -5.0, MIN_SIMULATIONS),
        ([10.0], 1_000.0, MIN_SIMULATIONS - 1),
        ([1.0] * 2_000, 1_000.0, MAX_WORK // 2_000 + 1),
    ],
)
def test_invalid_inputs_fail_closed_instead_of_defaulting(profits, equity, simulations) -> None:
    with pytest.raises(SimulationInputError):
        run_monte_carlo(profits, initial_equity=equity, simulations=simulations)


def test_monte_carlo_api_is_authenticated_rate_limited_and_provenanced(management_context) -> None:
    from tests.auth.helpers import bearer, csrf_headers, login_user, register_user

    context = management_context
    register_user(context, "quant@example.com")
    headers = bearer(login_user(context, "quant@example.com")["access_token"])
    payload = {"trade_results": MIXED, "initial_equity": 1000.0, "seed": 0, "data_source": "unit-test fixture"}
    path = "/api/v1/research/simulations/monte-carlo"

    assert context.client.post(path, json=payload).status_code == 401
    assert context.client.post(path, json=payload, headers=headers).status_code == 403  # CSRF
    response = context.client.post(path, json=payload, headers={**headers, **csrf_headers(context)})
    assert response.status_code == 200
    body = response.json()
    assert body["probability_of_profit"] == V3_MIXED["probability_of_profit"]
    assert body["confidence_interval_95"] == list(V3_MIXED["confidence_interval_95"])
    assert body["provenance"]["data_source"] == "unit-test fixture"
    assert body["provenance"]["execution_authority"] == "NONE"
    assert body["provenance"]["research_only"] is True

    invalid = context.client.post(
        path, json={**payload, "initial_equity": 0}, headers={**headers, **csrf_headers(context)}
    )
    assert invalid.status_code == 422
    too_small = context.client.post(
        path, json={**payload, "simulations": 10}, headers={**headers, **csrf_headers(context)}
    )
    assert too_small.status_code == 422

    statuses = [
        context.client.post(path, json=payload, headers={**headers, **csrf_headers(context)}).status_code
        for _ in range(6)
    ]
    assert 429 in statuses
